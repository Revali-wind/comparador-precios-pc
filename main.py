# main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import psycopg2
import psycopg2.extras

app = FastAPI(title="Comparador de Precios PC")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

DB_CONFIG = {
    "host": "localhost",
    "port": 5432,
    "dbname": "comparador_pc",
    "user": "comparador",
    "password": "comparador123",
}


def get_conn():
    return psycopg2.connect(**DB_CONFIG)


@app.get("/buscar")
def buscar(q: str, limite: int = 10):
    conn = get_conn()
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute("""
            SELECT
                p.id,
                p.nombre,
                p.marca,
                p.tienda,
                p.categoria,
                p.link,
                h.precio_transferencia,
                h.precio_otros_medios,
                h.precio_lista,
                h.consultado_en,
                similarity(p.nombre, %s) AS score
            FROM productos p
            JOIN LATERAL (
                SELECT *
                FROM precios_historial
                WHERE producto_id = p.id
                ORDER BY consultado_en DESC
                LIMIT 1
            ) h ON true
            WHERE similarity(p.nombre, %s) > 0.02
            ORDER BY score DESC
            LIMIT %s
        """, (q, q, limite))
        resultados = cur.fetchall()
    conn.close()
    return {"query": q, "resultados": resultados}


@app.get("/producto/{producto_id}/historial")
def historial(producto_id: int):
    conn = get_conn()
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute("""
            SELECT precio_transferencia, precio_otros_medios, precio_lista, consultado_en
            FROM precios_historial
            WHERE producto_id = %s
            ORDER BY consultado_en ASC
        """, (producto_id,))
        historial = cur.fetchall()
    conn.close()
    return {"producto_id": producto_id, "historial": historial}
