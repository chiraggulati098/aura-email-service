import re
from urllib.parse import urlparse
import pandas as pd
import joblib
import requests
from bs4 import BeautifulSoup

# Load the model from the specified directory
model_path = 'models/phishing_model.pkl'
model = joblib.load(model_path)

# Feature extraction function with all 27 features
def extract_features_from_url(url):
    parsed = urlparse(url)
    hostname = parsed.hostname or ""
    path = parsed.path or ""
    query = parsed.query or ""

    # Fetch webpage content with error handling
    try:
        response = requests.get(url, timeout=5, allow_redirects=True)
        soup = BeautifulSoup(response.text, 'html.parser')
        final_url = response.url  # For UrlLengthRT
    except Exception:
        soup = None
        final_url = url

    # 2. PctExtResourceUrls
    total_resources = 0
    external_resources = 0
    if soup:
        for tag in soup.find_all(['img', 'script', 'link'], src=True) + soup.find_all('link', href=True):
            total_resources += 1
            resource_url = urlparse(tag.get('src') or tag.get('href') or "").hostname or ""
            if resource_url and resource_url != hostname:
                external_resources += 1
        pct_ext_resource_urls = (external_resources / total_resources * 100) if total_resources > 0 else 0
    else:
        pct_ext_resource_urls = 0

    # 3. PctNullSelfRedirectHyperlinks
    total_links = 0
    null_self_redirects = 0
    if soup:
        for link in soup.find_all('a', href=True):
            total_links += 1
            href = link['href'].strip()
            if not href or href == "#" or href == url or href.startswith(f"{url}#"):
                null_self_redirects += 1
        pct_null_self_redirects = (null_self_redirects / total_links * 100) if total_links > 0 else 0
    else:
        pct_null_self_redirects = 0

    # 4. PctExtNullSelfRedirectHyperlinksRT
    total_links = 0
    ext_null_self_redirects = 0
    if soup:
        for link in soup.find_all('a', href=True):
            total_links += 1
            href = link['href'].strip()
            link_host = urlparse(href).hostname or ""
            if (not href or href == "#" or href == url or href.startswith(f"{url}#")) and link_host and link_host != hostname:
                ext_null_self_redirects += 1
        pct_ext_null_self_redirects_rt = (ext_null_self_redirects / total_links * 100) if total_links > 0 else 0
    else:
        pct_ext_null_self_redirects_rt = 0

    # 5. FrequentDomainNameMismatch
    mismatch_count = 0
    total_resources = 0
    if soup:
        for tag in soup.find_all(['a', 'img', 'script', 'link'], href=True, src=True):
            resource_url = urlparse(tag.get('href') or tag.get('src') or "").hostname or ""
            if resource_url and resource_url != hostname:
                mismatch_count += 1
            total_resources += 1
        frequent_domain_mismatch = (mismatch_count / total_resources) if total_resources > 0 else 0
    else:
        frequent_domain_mismatch = 0

    # 6. ExtMetaScriptLinkRT
    ext_meta_script_link = 0
    if soup:
        for tag in soup.find_all(['script', 'link'], src=True, href=True):
            resource_url = urlparse(tag.get('src') or tag.get('href') or "").hostname or ""
            if resource_url and resource_url != hostname:
                ext_meta_script_link = 1
                break
    else:
        ext_meta_script_link = 0

    # 7. SubmitInfoToEmail
    submit_to_email = 0
    if soup:
        for form in soup.find_all('form', action=True):
            action = form['action'].lower()
            if "@" in action and "." in action.split("@")[1]:
                submit_to_email = 1
                break
    else:
        submit_to_email = 0

    # 8. InsecureForms
    insecure_forms = 0
    if soup:
        for form in soup.find_all('form', action=True):
            action_url = urlparse(form['action'])
            if action_url.scheme and action_url.scheme.lower() != "https":
                insecure_forms = 1
                break
    else:
        insecure_forms = 0

    # 9. NumSensitiveWords
    sensitive_words = ["login", "password", "verify", "update", "account", "security", "reset"]
    num_sensitive_words = sum(1 for word in sensitive_words if word in url.lower())

    # 10. IframeOrFrame
    iframe_or_frame = 1 if soup and (soup.find('iframe') or soup.find('frame')) else 0

    # 11. AbnormalExtFormActionR
    abnormal_ext_form_action = 0
    if soup:
        for form in soup.find_all('form', action=True):
            action_host = urlparse(form['action']).hostname or ""
            if action_host and action_host != hostname:
                abnormal_ext_form_action = 1
                break
    else:
        abnormal_ext_form_action = 0

    # 12. UrlLengthRT
    url_length_rt = len(final_url)

    # 13. AbnormalFormAction
    abnormal_form_action = 0
    if soup:
        for form in soup.find_all('form', action=True):
            action_host = urlparse(form['action']).hostname or ""
            if action_host and (action_host != hostname or not action_host):
                abnormal_form_action = 1
                break
    else:
        abnormal_form_action = 0

    # 14. EmbeddedBrandName
    brands = ["paypal", "google", "amazon", "microsoft", "ebay", "apple", "bankofamerica", "facebook", "gitlab", "nordvpn", "shopify", "wellsfargo", "netflix"]
    embedded_brand_name = 1 if any(brand in hostname.lower() for brand in brands) else 0

    # Remaining computed features
    features = {
        "PctExtHyperlinks": 0,
        "PctExtResourceUrls": pct_ext_resource_urls,
        "PctNullSelfRedirectHyperlinks": pct_null_self_redirects,
        "PctExtNullSelfRedirectHyperlinksRT": pct_ext_null_self_redirects_rt,
        "NumNumericChars": sum(c.isdigit() for c in url),
        "FrequentDomainNameMismatch": frequent_domain_mismatch,
        "ExtMetaScriptLinkRT": ext_meta_script_link,
        "NumDash": url.count('-'),
        "SubmitInfoToEmail": submit_to_email,
        "NumDots": url.count('.'),
        "PathLength": len(path),
        "QueryLength": len(query),
        "PathLevel": path.count('/'),
        "InsecureForms": insecure_forms,
        "UrlLength": len(url),
        "NumSensitiveWords": num_sensitive_words,
        "NumQueryComponents": len(query.split('&')) if query else 0,
        "PctExtResourceUrlsRT": pct_ext_resource_urls,  # Using same as PctExtResourceUrls for simplicity
        "IframeOrFrame": iframe_or_frame,
        "HostnameLength": len(hostname),
        "NumAmpersand": url.count('&'),
        "AbnormalExtFormActionR": abnormal_ext_form_action,
        "UrlLengthRT": url_length_rt,
        "NumDashInHostname": hostname.count('-'),
        "IpAddress": int(re.match(r'\d+\.\d+\.\d+\.\d+', hostname or "") is not None),
        "AbnormalFormAction": abnormal_form_action,
        "EmbeddedBrandName": embedded_brand_name
    }

    return features

# Function to extract URLs from a string (email body)
def extract_urls_from_text(text):
    url_pattern = r'https?://[^\s<>"]+|www\.[^\s<>"]+'
    return re.findall(url_pattern, text)

# Function to process an email body and classify all URLs found
def process_email_body(email_body):
    urls = extract_urls_from_text(email_body)
    results = []
    for url in urls:
        try:
            label = _predict_single_url(url)
            results.append((url, label))
        except Exception as e:
            print(f"Failed to process URL: {url}\nError: {e}\n")
    return results

# Internal prediction function for a single URL
def _predict_single_url(url):
    features = extract_features_from_url(url)
    feature_df = pd.DataFrame([features])
    prediction = model.predict(feature_df)[0]
    label = "Phishing" if prediction == 1 else "Legitimate"
    return label

# Public prediction function
def predict_phishing(body):
    results = process_email_body(body)
    is_phishing = any(label == "Phishing" for _, label in results)
    return is_phishing