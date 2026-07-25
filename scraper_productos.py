# scraper_productos.py
import csv
import json
from playwright.sync_api import sync_playwright
from playwright_stealth import Stealth
from bs4 import BeautifulSoup

USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"


def extraer_precio_jsonld(html):
    soup = BeautifulSoup(html, "html.parser")
    scripts = soup.find_all("script", type="application/ld+json")

    for script in scripts:
        try:
            data = json.loads(script.string)
        except (json.JSONDecodeError, TypeError):
            continue

        items = data if isinstance(data, list) else [data]

        for item in items:
            if item.get("@type") == "Product":
                offers = item.get("offers", {})
                return {
                    "nombre": item.get("name"),
                    "marca": item.get("brand", {}).get("name"),
                    "precio": offers.get("price"),
                    "moneda": offers.get("priceCurrency"),
                    "disponibilidad": offers.get("availability"),
                    "sku": item.get("sku"),
                }
    return None


def limpiar_precio(texto):
    """Convierte '$267.990 7% DCTO.' -> 267990 (int)"""
    if not texto:
        return None
    # Nos quedamos solo con el primer número tipo $xxx.xxx
    import re
    match = re.search(r"\$[\d.]+", texto)
    if not match:
        return None
    numero = match.group().replace("$", "").replace(".", "")
    return int(numero) if numero.isdigit() else None
def extraer_precio_myshop(html):
    soup = BeautifulSoup(html, "html.parser")
    main_prices = soup.select("div.price > div.main-price")

    if not main_prices:
        return None

    def texto_directo(tag):
        # Solo el texto que está directo dentro del tag, sin entrar a hijos como <span>
        textos = [t for t in tag.find_all(string=True, recursive=False)]
        return " ".join(t.strip() for t in textos if t.strip())

    precio_transferencia = limpiar_precio(texto_directo(main_prices[0]))
    precio_otros_medios = limpiar_precio(texto_directo(main_prices[1])) if len(main_prices) > 1 else None

    normal_price_tag = soup.select_one("div.normal-price")
    precio_lista = limpiar_precio(normal_price_tag.get_text(strip=True)) if normal_price_tag else None

    # Usamos el título de la página como nombre (más confiable que adivinar el h1)
    title_tag = soup.select_one('meta[property="og:title"]')
    nombre = title_tag["content"] if title_tag else (soup.title.string if soup.title else None)

    return {
        "nombre": nombre,
        "marca": None,
        "precio": precio_transferencia,
        "precio_otros_medios": precio_otros_medios,
        "precio_lista": precio_lista,
        "moneda": "CLP",
        "disponibilidad": None,
        "sku": None,
    }



def extraer_precio(html, tienda):
    """Intenta JSON-LD primero; si falla, usa el extractor específico de la tienda."""
    producto = extraer_precio_jsonld(html)
    if producto:
        return producto

    if tienda == "myshop":
        return extraer_precio_myshop(html)

    return None


def procesar_csv(ruta_csv):
    resultados = []

    with Stealth().use_sync(sync_playwright()) as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page(user_agent=USER_AGENT)

        with open(ruta_csv, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            filas = list(reader)

        for fila in filas:
            link = fila["link"]
            print(f"Consultando: {link}")

            try:
                page.goto(link, wait_until="load", timeout=20000)
                page.wait_for_timeout(1500)
            except Exception as e:
                print(f"  Error al acceder: {e}")
                continue

            producto = extraer_precio(page.content(), fila["tienda"])

            if producto:
                producto["tienda"] = fila["tienda"]
                producto["categoria"] = fila["categoria"]
                producto["link"] = link
                resultados.append(producto)
                print(f"  OK: {producto['nombre']} -> ${producto['precio']}")
            else:
                print("  No se encontró precio en esta página.")

        browser.close()

    return resultados


def guardar_csv(resultados, ruta_salida):
    if not resultados:
        print("No hay resultados para guardar.")
        return

    columnas = ["tienda", "categoria", "nombre", "marca", "precio", "precio_otros_medios",
                "precio_lista", "moneda", "disponibilidad", "sku", "link"]

    with open(ruta_salida, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=columnas)
        writer.writeheader()
        for r in resultados:
            row = {col: r.get(col) for col in columnas}
            writer.writerow(row)

    print(f"Guardado en {ruta_salida}")


if __name__ == "__main__":
    resultados = procesar_csv("productos.csv")
    guardar_csv(resultados, "resultados.csv")
    print(f"\nTotal extraídos: {len(resultados)}")
