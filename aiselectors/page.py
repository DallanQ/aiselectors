import asyncio
import json
import re
from collections import Counter, defaultdict

from bs4 import BeautifulSoup, Comment
from cssselect import HTMLTranslator, SelectorError
from lxml import html as lxml_html
from lxml.etree import XPathEvalError


class Page:
    def __init__(self, url, html, ai_selectors):
        self.url = url
        self.html = html
        self.cleaned_html = _clean_html(html)
        self.ai_selectors = ai_selectors

    async def get_xpath(self, prompt, validators=None, verbose=False):
        """
        Get the xpath of the element that matches the prompt in the given html.
        """
        if validators is None:
            validators = []

        # look up cached xpath
        tree = lxml_html.fromstring(self.html)
        cached_xpath = self.ai_selectors.get_cache_entry(self.url, prompt)
        if cached_xpath and _is_valid_xpath(tree, cached_xpath, validators):
            return cached_xpath

        # get prompts for css, xpath, and text selectors, because sometimes they return different results
        css_prompt = _get_css_prompt(prompt, self.cleaned_html)
        xpath_prompt = _get_xpath_prompt(prompt, self.cleaned_html)
        text_prompt = _get_text_prompt(prompt, self.cleaned_html)
        # generate multiple prompts for each type, because the AI might not always return a valid selector
        prompts = (
            [css_prompt] * self.ai_selectors.n_css_attempts
            + [xpath_prompt] * self.ai_selectors.n_xpath_attempts
            + [text_prompt] * self.ai_selectors.n_text_attempts
        )

        # call openai in parallel with each prompt and get possible selectors
        responses = await _call_openai_multiple(
            self.ai_selectors.client,
            prompts,
            model=self.ai_selectors.model,
            max_tokens=self.ai_selectors.max_tokens,
        )
        if verbose:
            print("responses", responses)

        # get xpaths from responses
        xpaths = []
        response_texts = set()
        for response in responses:
            if "selector" in response:
                # convert css selector to xpath
                try:
                    xpath = HTMLTranslator().css_to_xpath(response["selector"])
                    if verbose:
                        print("selector", xpath)
                    xpaths.append(xpath)
                except SelectorError:
                    if verbose:
                        print("Invalid selector:", response["selector"])
            elif "xpath" in response:
                if verbose:
                    print("xpath", response["xpath"])
                xpaths.append(response["xpath"])
            elif "text" in response:
                text = response["text"]
                if verbose:
                    print("text", text)
                # convert text into generalized xpaths
                if isinstance(text, str):
                    response_texts.add(text)
                    for xpath in _get_xpaths_for_text(text, tree):
                        gen_xpath = _generalize_xpath(xpath, tree)
                        if verbose:
                            print("text xpath", gen_xpath, xpath)
                        xpaths.append(gen_xpath)
                elif isinstance(text, list):
                    response_texts.update(text)
                    text_xpaths = _get_xpaths_for_texts(text, tree)
                    if verbose:
                        print("texts xpaths", text_xpaths)
                    text_xpaths = _generalize_xpaths(text_xpaths, tree)
                    if verbose:
                        print("texts generalized xpaths", text_xpaths)
                    xpaths.extend(text_xpaths)

        # run validators on the xpaths
        valid_xpaths = set()
        for xpath in set(xpaths):
            if _is_valid_xpath(tree, xpath, validators):
                valid_xpaths.add(xpath)
                if verbose:
                    print("valid:", xpath)
            elif verbose:
                print("invalid:", xpath)

        # find the xpath that matches the most texts and is the most common and is shortest
        xpath_text_matches = Counter()
        for xpath in valid_xpaths:
            # count 1 for the xpath itself, in case none of the texts match
            xpath_text_matches[xpath] = 1
            elms = tree.xpath(xpath)
            for text in response_texts:
                if any(text in elm.text_content() for elm in elms):
                    xpath_text_matches[xpath] += 1
        if verbose:
            print("xpath_text_matches", xpath_text_matches)
        most_matches = None
        result_xpath = None
        for xpath, count in xpath_text_matches.most_common():
            if most_matches is None:
                most_matches = count
            if count < most_matches:
                break
            if (
                result_xpath is None
                or xpaths.count(result_xpath) < xpaths.count(xpath)
                or (xpaths.count(result_xpath) == xpaths.count(xpath) and len(xpath) < len(result_xpath))
            ):
                result_xpath = xpath

        # cache the xpath
        if result_xpath:
            self.ai_selectors.set_cache_entry(self.url, prompt, result_xpath)

        # return the xpath
        return result_xpath


def _is_valid_xpath(tree, xpath, validators):
    try:
        elements = tree.xpath(xpath)
        return all(validator(elements) for validator in validators)
    except XPathEvalError:
        return False


def _get_xpath_prompt(identifier, html):
    return f"""
    Please return a json object containing an xpath field equal to the xpath of the elements that match the following:

    ```
    {identifier}
    ```

    in the following html page

    ```
    {html}
    ```
    """


def _get_css_prompt(identifier, html):
    return f"""
    Please return a json object containing an selector field equal to the css selector of the elements that match the following:

    ```
    {identifier}
    ```

    in the following html page

    ```
    {html}
    ```
    """


def _get_text_prompt(identifier, html):
    return f"""
    Please return a json object containing a text field equal to the texts of the elements that match the following:

    ```
    {identifier}
    ```

    in the following html page

    ```
    {html}
    ```
    """


def _clean_html(html):
    """
    Remove comments, unnecessary, and hidden elements, and condense the remaining elements to reduce HTML tokens
    """

    soup = BeautifulSoup(html, "html.parser")

    # remove comments
    for elm in soup.find_all(string=lambda text: isinstance(text, Comment)):
        elm.extract()

    for elm in soup.find_all():
        # child of decomposed parent
        if elm is None or elm.attrs is None:
            continue
        # remove head, script, style, svg, and link tags and hidden elements
        if elm.name in ["head", "script", "style", "svg", "link"] or _is_hidden(elm):
            elm.decompose()
        else:
            # condense the remaining elements
            _condense(elm)

    return str(soup)


def _is_hidden(elm):
    """Return True if element is probably hidden."""

    if elm.get("hidden") is not None:
        return True
    if elm.get("data-styling-hidden") is not None:
        return True
    if elm.get("aria-hidden") == "true":
        return True
    if elm.get("type") == "hidden":
        return True
    if "ng-hide" in elm.get("class", []):
        return True
    for style in elm.get("style", "").replace(" ", "").split(";"):
        if style in ["display:none", "visibility:hidden", "opacity:0"]:
            return True
    return False


def _condense(elm):
    """
    Remove attributes that are probably not needed to identify elements for prompts.
    Also remove class names that contain digits, since these are often generated and not useful for identification.
    """

    all_attrs = list(elm.attrs.keys())
    for attr in all_attrs:
        if (
            attr not in ["id", "class", "href", "value"]
            and not attr.startswith("data-")
            and not attr.startswith("aria-")
        ):
            del elm[attr]
        elif attr == "class":
            elm["class"] = [cls for cls in elm.get("class") if not any(ch.isdigit() for ch in cls)]


def _get_xpaths_for_text(text, tree):
    # get all elements that contain the text
    if text.strip() == "":
        return []

    elms = []
    for element in tree.iter():
        if isinstance(element, lxml_html.HtmlElement) and element.text_content().strip() == text:
            elms.append(element)

    # keep only elements that don't have a child in elms
    base_elms = []
    for elm in elms:
        descendants = elm.iterdescendants()
        if not any(descendant in elms for descendant in descendants):
            base_elms.append(elm)

    # return xpaths for the base elements
    xpaths = []
    root_tree = tree.getroottree()
    for elm in base_elms:
        xpaths.append(root_tree.getpath(elm))
    return xpaths


def _generalize_xpath(xpath, tree):
    # get all elements that match the xpath
    elements = tree.xpath(xpath)
    # don't generalize unless the xpath is unique
    if len(elements) != 1:
        return xpath
    elm = elements[0]
    # if the element has a unique id that doesn't contain numbers, use that
    if "id" in elm.attrib and not any(ch.isdigit() for ch in elm.attrib["id"]):
        gen_xpath = f"//*[@id='{elm.attrib['id']}']"
        if len(tree.xpath(gen_xpath)) == 1:
            return gen_xpath
    # the following are commented out because they're not always unique across pages
    # if the element is an anchor tag with an href, use that
    # if elm.tag == 'a' and 'href' in elm.attrib:
    #     gen_xpath = f"//a[@href='{elm.attrib['href']}']"
    #     if len(tree.xpath(gen_xpath)) >= 1:
    #         return gen_xpath
    # if the element has unique text, use that
    # if elm.text:
    #     gen_xpath = f"//*[text()='{elm.text}']"
    #     if len(tree.xpath(gen_xpath)) == 1:
    #         return gen_xpath
    # if the element has a unique value, use that
    # if elm.get('value'):
    #     gen_xpath = f"//*[@value='{elm.get('value')}']"
    #     if len(tree.xpath(gen_xpath)) == 1:
    #         return gen_xpath
    # if the element has a unique aria label, use that
    if elm.get("aria-label"):
        gen_xpath = f"//*[@aria-label='{elm.get('aria-label')}']"
        if len(tree.xpath(gen_xpath)) == 1:
            return gen_xpath
    # if the element has a unique data-* attribute, use that
    for attr in elm.attrib:
        if attr.startswith("data-"):
            gen_xpath = f"//*[@{attr}='{elm.get(attr)}']"
            if len(tree.xpath(gen_xpath)) == 1:
                return gen_xpath
    # if the element has a unique class name that doesn't contain a digit, use that
    if elm.get("class"):
        for cls in elm.get("class").strip().split(" "):
            if not any(ch.isdigit() for ch in cls):
                gen_xpath = f"//*[contains(@class, '{cls}')]"
                if len(tree.xpath(gen_xpath)) == 1:
                    return gen_xpath
    return xpath


def _get_xpaths_for_texts(texts, tree):
    xpaths = []
    for text in texts:
        xpaths.extend(_get_xpaths_for_text(text, tree))
    return xpaths


def _generalize_xpaths(xpaths, tree):
    # group xpaths by tags without positions
    base_xpaths = defaultdict(list)
    for xpath in xpaths:
        base_xpath = re.sub(r"\[\d+\]", "", xpath)
        base_xpaths[base_xpath].append(xpath)

    # generalize xpaths by removing indices
    gen_xpaths = []
    for xpaths in base_xpaths.values():
        gen_components = xpaths[0].split("/")
        remove_indices = set()
        for xpath in xpaths[1:]:
            components = xpath.split("/")
            for i, component in enumerate(components):
                if component != gen_components[i]:
                    remove_indices.add(i)
        for i in remove_indices:
            gen_components[i] = re.sub(r"\[\d+\]", "", gen_components[i])
        gen_xpath = _generalize_xpath("/".join(gen_components), tree)
        gen_xpaths.append(gen_xpath)
    return gen_xpaths


def _call_openai(client, prompt, model, max_tokens, seed=None):
    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": prompt},
    ]
    response = client.chat.completions.create(
        model=model,
        response_format={"type": "json_object"},
        messages=messages,
        temperature=0.0,
        max_tokens=max_tokens,
        seed=seed,
    )
    try:
        return json.loads(response.choices[0].message.content)
    except json.JSONDecodeError:
        print("JSONDecodeError", response.choices[0].message.content)
        return {}


async def _call_openai_async(client, prompt, model, max_tokens, seed=None):
    return await asyncio.to_thread(
        _call_openai,
        client,
        prompt,
        model,
        max_tokens,
        seed,
    )


async def _call_openai_multiple(client, prompts, model, max_tokens=100):
    tasks = [_call_openai_async(client, prompt, model, max_tokens) for prompt in prompts]
    return await asyncio.gather(*tasks)
