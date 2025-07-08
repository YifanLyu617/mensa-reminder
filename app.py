from flask import Flask, render_template_string, request, redirect, url_for
import bs4, urllib.request, json, ssl
from datetime import date
from rapidfuzz import fuzz

ssl._create_default_https_context = ssl._create_unverified_context

FUZZY_THRESHOLD = 85

KEYWORDS_FILE = "keywords.json"

CATEGORY_SYNONYMS = {
    "nudeln": ["pasta", "spaghetti", "teigwaren", "maccheroni", "lasagne", "tagliatelle", "penne"],
    "reis": ["reis", "basmatireis", "wildreis", "jasminreis"],
    "kartoffeln": ["kartoffel", "pommes", "kartoffelbrei", "kartoffelsalat", "bratkartoffeln", "rosenkartoffeln"],
    "hähnchen": ["huhn", "poulet", "hähnchenbrust", "pouletbrust", "hähnchenfleisch"],
    "rind": ["rindfleisch", "rind", "rinderfilet", "rinderhack", "rinderbraten"],
    "schwein": ["schweinefleisch", "schwein", "schweineschnitzel", "schweinebraten"],
    "fisch": ["fisch", "lachs", "forelle", "seelachs", "fischfilet"],
    "vegan": ["vegetarisch", "pflanzlich", "gemüse", "salat", "tofu", "falafel"],
    "asiatisch": ["japanisch", "chinesisch", "thai", "koreanisch", "vietnamesisch", "indisch", "indonesisch"],
    "käse": ["käse", "emmentaler", "schafskäse", "mozarella", "parmesan"],
    "dessert": ["nachtisch", "kuchen", "pudding", "creme", "eis", "torte", "apfelstrudel"],
    "burger": ["burger", "hamburger", "cheeseburger", "veggie burger", "chicken burger"],
    "pizza": ["pizza", "fladenbrotpizza", "margherita", "pepperoni", "vegetarisch pizza"],
    "dip": ["dip", "soße", "sauce", "dressing", "ketchup", "mayonnaise", "senf"],
}

MENSA_URLS = {
    "Hauptmensa": "https://www.studentenwerk-oberfranken.de/essen/speiseplaene/bayreuth/hauptmensa/tag/",
    "Frischraum": "https://www.studentenwerk-oberfranken.de/essen/speiseplaene/bayreuth/frischraum/tag/",
}

app = Flask(__name__)

def load_keywords():
    try:
        with open(KEYWORDS_FILE, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return []

def save_keywords(keywords):
    with open(KEYWORDS_FILE, "w") as f:
        json.dump(keywords, f)

def get_today_date():
    return date.today().strftime("%Y-%m-%d")

def scrape_menus():
    today_date = get_today_date()
    menus = {}
    for mensa_name, base_url in MENSA_URLS.items():
        full_url = base_url + today_date + ".html"
        try:
            response = urllib.request.urlopen(full_url)
            webpage = response.read()
            soup = bs4.BeautifulSoup(webpage, "html.parser")
            items = []
            hauptgerichte_divs = soup.find_all("div", class_="tx-bwrkspeiseplan__hauptgerichte")
            for div in hauptgerichte_divs:
                tables = div.find_all("table", class_="tx-bwrkspeiseplan__table-meals")
                for table in tables:
                    rows = table.find_all("tr")
                    for row in rows:
                        td = row.find("td")
                        if td:
                            td_copy = td.__copy__()
                            for sup in td_copy.find_all("sup"):
                                sup.decompose()
                            meal_text = ''.join(td_copy.find_all(string=True, recursive=False)).strip()
                            meal_text = ' '.join(meal_text.split())
                            if meal_text:
                                items.append(meal_text)
            menus[mensa_name] = list(dict.fromkeys(items))
        except Exception as e:
            print(f"[ERROR] {mensa_name}: {e}")
            menus[mensa_name] = []
    return menus

@app.route("/", methods=["GET", "POST"])
def index():
    keywords = load_keywords()
    matches_found = {}

    if request.method == "POST":
        action = request.form.get("action")
        if action == "add":
            keyword = request.form.get("keyword", "").strip()
            if keyword:
                keywords.append(keyword)
                save_keywords(keywords)
            return redirect(url_for("index"))

        elif action == "clear":
            save_keywords([])
            return redirect(url_for("index"))

        elif action == "check":
            menus = scrape_menus()
            for mensa_name, items in menus.items():
                matches = []
                for item in items:
                    item_lower = item.lower()
                    for keyword in keywords:
                        keyword_lower = keyword.lower()
                        if keyword_lower in item_lower:
                            matches.append(f"{item} (direct match)")
                            break
                        synonyms = CATEGORY_SYNONYMS.get(keyword_lower, [])
                        if any(syn in item_lower for syn in synonyms):
                            matches.append(f"{item} (category match)")
                            break
                        score = fuzz.partial_ratio(keyword_lower, item_lower)
                        if score >= FUZZY_THRESHOLD:
                            matches.append(f"{item} (fuzzy match, score: {score})")
                            break
                        
                if matches:
                    matches_found[mensa_name] = list(dict.fromkeys(matches))

    return render_template_string(TEMPLATE, keywords=keywords, matches_found=matches_found)

TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Bayreuth Mensa Reminder</title>
</head>
<body>
    <h1>Bayreuth Mensa Reminder</h1>
    <form method="post">
        <input type="text" name="keyword" placeholder="Enter dish keyword" required>
        <button type="submit" name="action" value="add">Add Keyword</button>
    </form>
    <h3>Saved Keywords:</h3>
    <ul>
        {% for keyword in keywords %}
            <li>{{ keyword }}</li>
        {% endfor %}
    </ul>
    <form method="post">
        <button type="submit" name="action" value="check">Check Mensa Menus Now</button>
        <button type="submit" name="action" value="clear">Clear All Keywords</button>
    </form>
    {% if matches_found %}
        <h2>Matches Found:</h2>
        {% for mensa_name, matches in matches_found.items() %}
            <h3>{{ mensa_name }}</h3>
            <ul>
                {% for match in matches %}
                    <li>{{ match }}</li>
                {% endfor %}
            </ul>
        {% endfor %}
    {% endif %}
</body>
</html>
"""

import os

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)