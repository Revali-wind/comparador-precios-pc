# scraper_spdigital.py — usando type() en vez de fill()
from playwright.sync_api import sync_playwright
from playwright_stealth import Stealth
from bs4 import BeautifulSoup

BASE_URL = "https://www.spdigital.cl"

def buscar_productos(query: str):
    with Stealth().use_sync(sync_playwright()) as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )

        print("Cargando página principal...")
        page.goto(BASE_URL, wait_until="networkidle")
        page.wait_for_timeout(2000)

        search_input = page.locator(
            'input[placeholder="Busca los mejores productos y marcas :)"]:visible'
        )
        search_input.first.click()
        page.wait_for_timeout(300)

        print(f"Escribiendo '{query}' letra por letra...")
        search_input.first.type(query, delay=100)  # simula tipeo real, letra por letra
        page.wait_for_timeout(800)

        print("Presionando Enter con el teclado de la página...")
        page.keyboard.press("Enter")  # a nivel de página, no del elemento

        page.wait_for_url("**/search/**", timeout=10000)
        print(f"Navegó a: {page.url}")

        print("Esperando a que carguen los productos...")
        page.wait_for_selector(".Fractal-ProductCard__productcard--container", timeout=20000)
        page.wait_for_timeout(1000)

        html = page.content()
        browser.close()

    soup = BeautifulSoup(html, "html.parser")
    cards = soup.select(".Fractal-ProductCard__productcard--container")

    resultados = []
    for card in cards:
        marca_tag = card.select_one(".Fractal-ProductCard--productDetailsContainer a")
        marca = marca_tag.get_text(strip=True) if marca_tag else None

        nombre_tag = card.select_one(".Fractal-ProductCard--productDescriptionTextContainer a")
        nombre = nombre_tag.get_text(strip=True) if nombre_tag else None
        link = BASE_URL + nombre_tag["href"] if nombre_tag else None

        price_variants = card.select(".Fractal-ProductCard--priceVariantContainer .Fractal-Price--price")
        precio_transferencia = price_variants[0].get_text(strip=True) if len(price_variants) > 0 else None
        precio_otros_medios = price_variants[1].get_text(strip=True) if len(price_variants) > 1 else None

        old_price_tag = card.select_one(".Fractal-Price__price--strikethrough")
        precio_lista = None
        if old_price_tag and "Fractal-ProductCard--invisible" not in old_price_tag.get("class", []):
            precio_lista = old_price_tag.get_text(strip=True)

        resultados.append({
            "marca": marca,
            "nombre": nombre,
            "link": link,
            "precio_transferencia": precio_transferencia,
            "precio_otros_medios": precio_otros_medios,
            "precio_lista": precio_lista,
        })

    return resultados


if __name__ == "__main__":
    productos = buscar_productos("rtx 4070")
    print(f"\nEncontrados: {len(productos)} productos\n")
    for p in productos:
        print(p)
