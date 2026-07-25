# scraper_productos.py
import csv
import json
import re
import psycopg2
from playwright.sync_api import sync_playwright
from playwright_stealth import Stealth
from bs4 import BeautifulSoup

USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

DB_CONFIG = {
    "host": "localhost",
    "port": 5432,
    "dbname": "comparador_pc",
    "user": "comparador",
    "password": "comparador123",
}


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
                    "precio_otros_medios": None,
                    "precio_lista": None,
                    "disponibilidad": offers.get("availability"),
                    "sku": item.get("sku"),
                }
    return None


def limpiar_precio(texto):
    if not texto:
        return None
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
        textos = [t for t in tag.find_all(string=True, recursive=False)]
        return " ".join(t.strip() for t in textos if t.strip())

    precio_transferencia = limpiar_precio(texto_directo(main_prices[0]))
    precio_otros_medios = limpiar_precio(texto_directo(main_prices[1])) if len(main_prices) > 1 else None

    normal_price_tag = soup.select_one("div.normal-price")
    precio_lista = limpiar_precio(normal_price_tag.get_text(strip=True)) if normal_price_tag else None

    title_tag = soup.select_one('meta[property="og:title"]')
    nombre = title_tag["content"] if title_tag else (soup.title.string if soup.title else None)

    return {
        "nombre": nombre,
        "marca": None,
        "precio": precio_transferencia,
        "precio_otros_medios": precio_otros_medios,
        "precio_lista": precio_lista,
        "disponibilidad": None,
        "sku": None,
    }


def extraer_precio(html, tienda):
    producto = extraer_precio_jsonld(html)
    if producto:
        return producto
    if tienda == "myshop":
        return extraer_precio_myshop(html)
    return None


def guardar_en_db(conn, tienda, categoria, link, producto):
    with conn.cursor() as cur:
        # Insertamos el producto si no existe (link es UNIQUE), o lo dejamos igual si ya está
        cur.execute("""
            INSERT INTO productos (tienda, categoria, nombre, marca, sku, link)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (link) DO UPDATE SET nombre = EXCLUDED.nombre
            RETURNING id
        """, (tienda, categoria, producto["nombre"], producto["marca"], producto["sku"], link))
        producto_id = cur.fetchone()[0]

        # Cada corrida agrega una fila nueva de precio (así se arma el historial)
        cur.execute("""
            INSERT INTO precios_historial
                (producto_id, precio_transferencia, precio_otros_medios, precio_lista, disponibilidad)
            VALUES (%s, %s, %s, %s, %s)
        """, (producto_id, producto["precio"], producto["precio_otros_medios"],
              producto["precio_lista"], producto["disponibilidad"]))

    conn.commit()


def procesar_csv(ruta_csv):
    conn = psycopg2.connect(**DB_CONFIG)
    total_guardados = 0

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
                guardar_en_db(conn, fila["tienda"], fila["categoria"], link, producto)
                total_guardados += 1
                print(f"  OK: {producto['nombre']} -> ${producto['precio']}")
            else:
                print("  No se encontró precio en esta página.")

        browser.close()

    conn.close()
    return total_guardados


if __name__ == "__main__":
    total = procesar_csv("productos.csv")
    print(f"\nTotal guardado en la base de datos: {total}")
