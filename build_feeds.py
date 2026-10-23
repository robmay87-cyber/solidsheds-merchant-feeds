#!/usr/bin/env python3
"""Build Google Merchant Center feeds for Solid Sheds from the live Wix store
(public product pages + their schema.org data, which Wix generates from the store).
No prices are invented: every price comes from the Wix product page."""
import csv, html, json, re, sys, urllib.request, datetime, os
SITE = "https://www.solidsheds.co.nz"
STORE_CODE = "SOLIDSHEDS1"
OUT = sys.argv[1] if len(sys.argv) > 1 else "public"
SKIP_WORDS = ("rent", "rental", "hire", "trailer")
BAN = re.compile(r"colou?r\s*steel|colorsteel", re.I)

def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 SolidShedsFeedBot"})
    return urllib.request.urlopen(req, timeout=30).read().decode("utf-8", "replace")

def clean_desc(text):
    lines = []
    for ln in text.replace("\r", "").split("\n"):
        ln = ln.strip()
        if not ln or BAN.search(ln) or "youtu" in ln:
            continue
        lines.append(ln)
    d = " ".join(lines)
    d = re.sub(r"\s+", " ", d).strip()
    return d[:4900]

os.makedirs(OUT, exist_ok=True)
locs = re.findall(r"<loc>([^<]+)</loc>", get(SITE + "/store-products-sitemap.xml"))
products, skipped = [], []
for url in locs:
    slug = url.rsplit("/", 1)[-1]
    if any(w in slug.lower() for w in SKIP_WORDS):
        skipped.append((slug, "hire/rental item, not a product for sale")); continue
    page = get(url)
    ld = None
    for m in re.findall(r'<script type="application/ld\+json"[^>]*>(.*?)</script>', page, re.S):
        try:
            d = json.loads(m)
        except Exception:
            continue
        if d.get("@type") == "Product":
            ld = d
    if not ld:
        skipped.append((slug, "no product data (price) published on the page")); continue
    name = html.unescape(ld.get("name", "")).strip()
    if any(w in name.lower() for w in SKIP_WORDS):
        skipped.append((slug, "hire/rental item")); continue
    offers = ld.get("offers") or {}
    if isinstance(offers, list): offers = offers[0]
    price = offers.get("price") or offers.get("lowPrice")
    if not price:
        skipped.append((slug, "no price on page")); continue
    desc = clean_desc(ld.get("description", ""))
    if "door" in name.lower() and "white" not in ld.get("description", "").lower():
        skipped.append((slug, "door not listed as white")); continue
    imgs = [i.get("contentUrl", "").split("/v1/")[0] for i in ld.get("image", []) if isinstance(i, dict)]
    avail = "in_stock" if "InStock" in offers.get("availability", "") else ("preorder" if "PreOrder" in offers.get("availability", "") else "out_of_stock")
    products.append({
        "id": slug, "title": BAN.sub("steel", name), "description": desc or name,
        "link": url, "image_link": imgs[0] if imgs else "",
        "additional_image_link": ",".join(imgs[1:10]),
        "availability": avail, "price": f"{float(price):.2f} NZD",
        "brand": "Solid Sheds", "condition": "new", "identifier_exists": "no",
        "color": "White" if "door" in name.lower() else "",
    })

pf = ["id","title","description","link","image_link","additional_image_link","availability","price","brand","condition","identifier_exists","color"]
with open(f"{OUT}/products.tsv", "w", newline="") as f:
    w = csv.DictWriter(f, pf, delimiter="\t"); w.writeheader(); w.writerows(products)
with open(f"{OUT}/local_inventory.tsv", "w", newline="") as f:
    w = csv.writer(f, delimiter="\t")
    w.writerow(["store_code","id","availability","price","pickup_method","pickup_sla"])
    for p in products:
        w.writerow([STORE_CODE, p["id"], p["availability"], p["price"],
                    "buy" if p["availability"] == "in_stock" else "not supported",
                    "same day" if p["availability"] == "in_stock" else ""])
with open(f"{OUT}/index.html", "w") as f:
    f.write(f"<p>Solid Sheds Merchant feeds. Updated {datetime.datetime.now(datetime.timezone.utc).isoformat()}. "
            f"{len(products)} products.</p><ul><li><a href='products.tsv'>products.tsv</a></li>"
            f"<li><a href='local_inventory.tsv'>local_inventory.tsv</a></li></ul>")
print(f"products={len(products)}")
for s in skipped: print("SKIPPED", *s)
