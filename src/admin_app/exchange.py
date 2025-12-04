from __future__ import annotations

"""
Utilidades de tipo "exchange" para obtener la tasa cambiaria (Bs/USD).

Nota importante:
- Se intentan múltiples fuentes públicas no oficiales como respaldo.
- Esta función puede fallar si no hay internet o cambia el formato de la API.
- Devuelve un float (Bs por 1 USD) o None si no se pudo obtener.

No se realizan llamadas en segundo plano; quien la use debería ejecutarla en un
hilo o aceptar un bloqueo breve del UI durante la petición.
"""

from typing import Optional, Dict
import os
import json
import time
from pathlib import Path
from datetime import date as _date, datetime as _dt

try:
	import requests  # type: ignore
except Exception:  # requests puede no estar instalado aún
	requests = None  # type: ignore


def _try_get(url: str, json_path: tuple[str, ...], timeout: float = 5.0) -> Optional[float]:
	"""Realiza GET a url y navega por json_path para extraer un número.

	json_path: tupla de claves para llegar al valor deseado.
	Devuelve el valor como float si es válido (>0), o None.
	"""
	if requests is None:
		return None
	try:
		resp = requests.get(url, timeout=timeout)
		if resp.status_code != 200:
			return None
		data = resp.json()
		cur = data
		for k in json_path:
			if isinstance(cur, dict) and k in cur:
				cur = cur[k]
			else:
				return None
		try:
			val = float(cur)
			return val if val > 0 else None
		except Exception:
			return None
	except Exception:
		return None


def _extract_rate_generic(data: object) -> Optional[float]:
	"""Extrae un número de tasa común desde diferentes estructuras JSON.

	Intenta llaves frecuentes: 'valor', 'price', 'promedio', 'value', 'rate'.
	Si es una lista, intenta encontrar elementos con nombre/tipo que contenga 'bcv' u 'oficial'.
	"""
	keys = ("valor", "price", "promedio", "value", "rate")
	try:
		if isinstance(data, dict):
			# Si el dict contiene directamente una de las llaves comunes
			for k in keys:
				if k in data:
					try:
						v = float(data[k])
						return v if v > 0 else None
					except Exception:
						continue
			# Buscar en subniveles poco profundos
			for v in data.values():
				if isinstance(v, dict):
					r = _extract_rate_generic(v)
					if r:
						return r
				elif isinstance(v, list):
					r = _extract_rate_generic(v)
					if r:
						return r
		elif isinstance(data, list):
			# Buscar un item relacionado a BCV u Oficial
			def looks_like_bcv(item: dict) -> bool:
				txts = []
				for k, v in item.items():
					if isinstance(v, str) and k.lower() in ("nombre", "casa", "tipo", "indicador", "fuente", "title", "name"):
						txts.append(v.lower())
				joined = " ".join(txts)
				return ("bcv" in joined) or ("oficial" in joined)

			for it in data:
				if isinstance(it, dict) and looks_like_bcv(it):
					for k in keys:
						if k in it:
							try:
								v = float(it[k])
								return v if v > 0 else None
							except Exception:
								continue
			# Si no se identifica, probar el primero
			for it in data:
				if isinstance(it, dict):
					for k in keys:
						if k in it:
							try:
								v = float(it[k])
								return v if v > 0 else None
							except Exception:
								continue
		return None
	except Exception:
		return None


def _try_dolarapi(timeout: float = 5.0) -> Optional[float]:
	if requests is None:
		return None
	endpoints = [
		"https://ve.dolarapi.com/v1/dolares/oficial",
		"https://ve.dolarapi.com/v1/dolares/bcv",
		"https://ve.dolarapi.com/v1/dolares",
	]
	for url in endpoints:
		try:
			resp = requests.get(url, timeout=timeout)
			if resp.status_code != 200:
				continue
			data = resp.json()
			rate = _extract_rate_generic(data)
			if rate and rate > 0:
				return rate
		except Exception:
			continue
	return None


def _cache_path() -> Path:
	# data/bcv_rate.json en la raíz del repo
	# __file__ -> src/admin_app/exchange.py; parents[1] = src, parents[2] = repo root
	root = Path(__file__).resolve().parents[2]
	data_dir = root / "data"
	try:
		data_dir.mkdir(parents=True, exist_ok=True)
	except Exception:
		pass
	return data_dir / "bcv_rate.json"


def _save_cached_rate(rate: float) -> None:
	try:
		if rate and rate > 0:
			payload = {"rate": float(rate), "ts": int(time.time())}
			_cache_path().write_text(json.dumps(payload), encoding="utf-8")
	except Exception:
		pass


def _load_cached_rate(max_age_seconds: int | None = 7 * 24 * 3600) -> Optional[float]:
	try:
		p = _cache_path()
		if not p.exists():
			return None
		data = json.loads(p.read_text(encoding="utf-8"))
		rate = float(data.get("rate", 0))
		ts = int(data.get("ts", 0))
		if rate <= 0:
			return None
		if max_age_seconds is not None and ts > 0:
			if (time.time() - ts) > max_age_seconds:
				return None
		return rate
	except Exception:
		return None


def _load_default_rate() -> Optional[float]:
	# 1) Variable de entorno BCV_RATE_DEFAULT
	env_def = os.getenv("BCV_RATE_DEFAULT")
	if env_def:
		try:
			val = float(env_def)
			if val > 0:
				return val
		except Exception:
			pass
	# 2) Archivo data/default_bcv_rate.txt con un número
	try:
		root = Path(__file__).resolve().parents[2]
		fp = (root / "data" / "default_bcv_rate.txt")
		if fp.exists():
			txt = fp.read_text(encoding="utf-8").strip().replace(",", ".")
			val = float(txt)
			return val if val > 0 else None
	except Exception:
		pass
	return None


def get_bcv_rate(timeout: float = 5.0) -> Optional[float]:
	"""Obtiene la tasa del BCV (Bs por USD) desde varias fuentes.

	Orden de intento:
	1) Variable de entorno DOLLAR_API_URL + DOLLAR_API_JSON_PATH (opcional)
	2) API pública pydolarvenezuela (no oficial)
	3) DolarToday (no oficial) – promedio en Bs por USD

	Retorna:
		float con tasa (Bs/USD) o None.
	"""
	# 1) Fuente configurable por entorno
	env_url = os.getenv("DOLLAR_API_URL")
	env_path = os.getenv("DOLLAR_API_JSON_PATH")  # e.g. "data,BCV,price"
	if env_url and env_path:
		json_path = tuple([p.strip() for p in env_path.split(",") if p.strip()])
		val = _try_get(env_url, json_path, timeout=timeout)
		if val:
			_save_cached_rate(val)
			try:
				_save_daily_rate_today(val)
			except Exception:
				pass
			return val

	# 2) ve.dolarapi.com (preferida)
	val = _try_dolarapi(timeout=timeout)
	if val:
		_save_cached_rate(val)
		try:
			_save_daily_rate_today(val)
		except Exception:
			pass
		return val

	# 3) pydolarvenezuela API (variante vercel) – estructura esperada: { "monitors": { "bcv": { "price": 40.1 }}}
	# Referencia (puede cambiar): https://pydolarvenezuela-api.vercel.app
	val = _try_get(
		"https://pydolarvenezuela-api.vercel.app/api/v1/dollar",
		("monitors", "bcv", "price"),
		timeout=timeout,
	)
	if val:
		_save_cached_rate(val)
		try:
			_save_daily_rate_today(val)
		except Exception:
			pass
		return val

	# 4) DolarToday (no oficial) – estructura: { "USD": { "promedio": 40.1, ... } }
	val = _try_get(
		"https://s3.amazonaws.com/dolartoday/data.json",
		("USD", "promedio"),
		timeout=timeout,
	)
	if val:
		_save_cached_rate(val)
		return val

	# 5) Caché local (última tasa válida, hasta 7 días)
	cached = _load_cached_rate()
	if cached:
		return cached

	# 6) Valor por defecto configurable (env o archivo en data/)
	default_val = _load_default_rate()
	if default_val:
		return default_val

	return None


# === Histórico por día ===
def _rates_path() -> Path:
	root = Path(__file__).resolve().parents[2]
	data_dir = root / "data"
	try:
		data_dir.mkdir(parents=True, exist_ok=True)
	except Exception:
		pass
	return data_dir / "bcv_rates.json"


def _load_rates_map() -> Dict[str, float]:
	try:
		p = _rates_path()
		if not p.exists():
			return {}
		data = json.loads(p.read_text(encoding="utf-8"))
		if isinstance(data, dict):
			# normalizar a float
			result: Dict[str, float] = {}
			for k, v in data.items():
				try:
					f = float(v)
					if f > 0:
						result[k] = f
				except Exception:
					continue
			return result
		return {}
	except Exception:
		return {}


def _save_rates_map(mp: Dict[str, float]) -> None:
	try:
		_rates_path().write_text(json.dumps(mp, ensure_ascii=False, indent=2), encoding="utf-8")
	except Exception:
		pass


def _save_daily_rate_today(rate: float) -> None:
	if not (rate and rate > 0):
		return
	mp = _load_rates_map()
	today = _date.today().isoformat()
	# no sobreescribir si ya existe con un valor cercano mayor a 0 (pero aquí sí actualizamos por simplicidad)
	mp[today] = float(rate)
	_save_rates_map(mp)


def set_rate_for_date(d: _date, rate: float) -> None:
	if not (rate and rate > 0):
		return
	mp = _load_rates_map()
	mp[d.isoformat()] = float(rate)
	_save_rates_map(mp)


def get_rate_for_date(d: _date, timeout: float = 5.0) -> Optional[float]:
	"""Obtiene la tasa para la fecha dada.

	- Si la fecha es hoy: consulta fuentes (get_bcv_rate) y guarda; si falla, usa caché/por defecto.
	- Si es pasada/futura: intenta leer del histórico local; si no hay valor, retorna None.
	"""
	if d == _date.today():
		val = get_bcv_rate(timeout=timeout)
		# get_bcv_rate ya guarda en histórico y caché
		return val
	# Buscar en histórico local
	mp = _load_rates_map()
	if d.isoformat() in mp:
		return mp[d.isoformat()]
	# Si no hay, como último recurso retorna None para que la UI decida
	return None

