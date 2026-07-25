CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE TABLE productos (
    id SERIAL PRIMARY KEY,
    tienda TEXT NOT NULL,
    categoria TEXT NOT NULL,
    nombre TEXT NOT NULL,
    marca TEXT,
    sku TEXT,
    link TEXT NOT NULL UNIQUE,
    creado_en TIMESTAMP DEFAULT NOW()
);

CREATE TABLE precios_historial (
    id SERIAL PRIMARY KEY,
    producto_id INTEGER NOT NULL REFERENCES productos(id) ON DELETE CASCADE,
    precio_transferencia NUMERIC,
    precio_otros_medios NUMERIC,
    precio_lista NUMERIC,
    disponibilidad TEXT,
    consultado_en TIMESTAMP DEFAULT NOW()
);

-- Índice para búsqueda difusa por nombre (tolerante a errores tipográficos)
CREATE INDEX idx_productos_nombre_trgm ON productos USING GIN (nombre gin_trgm_ops);
