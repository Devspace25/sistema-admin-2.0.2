from __future__ import annotations

from pathlib import Path
from datetime import datetime
import json


def _data_dir() -> Path:
    d = Path.cwd() / "data" / "receipts"
    d.mkdir(parents=True, exist_ok=True)
    return d


def print_receipt_80mm(*, order_code: str, product_name: str, total_usd: float, payment_method: str | None,
                       advisor: str | None, summary: str | None, details: dict | None) -> Path:
    """Genera un recibo de 80mm en texto plano. Devuelve la ruta del archivo creado.

    - order_code: p. ej., ORD-20250101-000123
    - details: parámetros del corpóreo (para auditoría)
    """
    now = datetime.now().strftime('%Y-%m-%d %H:%M')
    lines: list[str] = []
    lines.append("CENTRO DE IMPRESIÓN")
    lines.append("RIF: J-00000000-0")
    lines.append("TEL: 000-0000000")
    lines.append("-")
    lines.append(f"ORDEN: {order_code}")
    lines.append(f"FECHA: {now}")
    if advisor:
        lines.append(f"ASESOR: {advisor}")
    lines.append("-")
    lines.append(f"PRODUCTO: {product_name}")
    lines.append("-")
    pay = payment_method or ""
    lines.append(f"PAGO: {pay}")
    lines.append(f"TOTAL: $ {total_usd:.2f}")
    lines.append("-")
    lines.append("¡Gracias por su compra!")
    lines.append("")
    # Guardar
    out = _data_dir() / f"{order_code}.txt"
    out.write_text("\n".join(lines), encoding="utf-8")
    # Opcional: guardar JSON de detalles (auditoría)
    if details is not None:
        (out.with_suffix('.json')).write_text(json.dumps(details, ensure_ascii=False, indent=2), encoding='utf-8')
    return out


def _wrap_text(text: str, width: int = 32) -> list[str]:
    words = text.split()
    lines: list[str] = []
    cur: list[str] = []
    cur_len = 0
    for w in words:
        if cur_len + len(w) + (1 if cur else 0) > width:
            lines.append(" ".join(cur))
            cur = [w]
            cur_len = len(w)
        else:
            if cur:
                cur_len += 1 + len(w)
            else:
                cur_len = len(w)
            cur.append(w)
    if cur:
        lines.append(" ".join(cur))
    return lines


def _to_float(value: object, default: float = 0.0) -> float:
    """Convierte cualquier valor a float, devolviendo *default* si falla."""
    try:
        if value is None:
            return default
        if isinstance(value, str):
            cleaned = value.replace('.', '').replace(',', '.').strip()
            if cleaned:
                return float(cleaned)
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _format_bs(value: float) -> str:
    """Formatea un monto en bolívares con separador de miles y coma decimal."""
    amount = round(value or 0.0, 2)
    formatted = f"{amount:,.2f}"
    # Cambiar puntos por comas respetando separadores
    return formatted.replace(',', '¤').replace('.', ',').replace('¤', '.')


def print_order_80mm(*, order_id: int, sale_id: int, product_name: str, status: str, details_json: str) -> Path:
    """Genera un ticket de orden de producción (80mm) con detalles técnicos.

    - order_id: ID interno del pedido
    - sale_id: ID de la venta
    - product_name: nombre del producto
    - status: estado del pedido
    - details_json: JSON con los parámetros técnicos
    """
    now = datetime.now().strftime('%Y-%m-%d %H:%M')
    lines: list[str] = []
    lines.append("ORDEN DE PRODUCCIÓN")
    lines.append("-")
    lines.append(f"Pedido: #{order_id}")
    lines.append(f"Venta: #{sale_id}")
    lines.append(f"Fecha: {now}")
    lines.append(f"Producto: {product_name}")
    if status:
        lines.append(f"Estado: {status}")
    lines.append("-")
    # Detalles técnicos (estructura nueva esperada)
    try:
        details = json.loads(details_json or "{}")
    except Exception:
        details = {}

    # Try to load sale info (descripcion, forma_pago, diseno_usd, pagos)
    sale_info = {}
    try:
        from .db import make_session_factory
        from .models import Sale
        SF = make_session_factory()
        with SF() as ss:
            s_obj = ss.get(Sale, int(sale_id)) if sale_id else None
            if s_obj:
                sale_info = {
                    'descripcion': getattr(s_obj, 'descripcion', None),
                    'forma_pago': getattr(s_obj, 'forma_pago', None),
                    'diseno_usd': float(getattr(s_obj, 'diseno_usd', 0.0) or 0.0),
                    'ingresos_usd': float(getattr(s_obj, 'ingresos_usd', 0.0) or 0.0),
                    'abono_usd': float(getattr(s_obj, 'abono_usd', 0.0) or 0.0),
                    'venta_usd': float(getattr(s_obj, 'venta_usd', 0.0) or 0.0),
                    'restante': float(getattr(s_obj, 'restante', 0.0) or 0.0),
                }
    except Exception:
        sale_info = {}

    # If the details payload also contains descripcion_text or incluye_diseno, prefer them
    if 'descripcion_text' in details or 'items' in details:
        desc = details.get('descripcion_text') or ''
        if desc:
            lines.append("DESCRIPCION:")
            for l in _wrap_text(desc, 40):
                lines.append(l)
            lines.append("-")
        # override sale_info descripcion if present in details
        if desc:
            sale_info['descripcion'] = desc

        items = details.get('items') or []
        if items:
            lines.append("CANT  DESCRIPCION           SUBT$")
            for it in items:
                c = it.get('cantidad', 1)
                pu = it.get('precio_unitario', 0.0)
                sub = it.get('subtotal_usd', pu * c)
                lines.append(f"{c:>4}  {product_name[:18]:18}  ${sub:8.2f}")
            lines.append("-")

        totals = details.get('totals') or {}
        if totals:
            lines.append(f"TOTAL: $ {float(totals.get('total_usd', 0.0)):.2f}")
            lines.append(f"TOTAL Bs: {float(totals.get('total_bs', 0.0)):.2f}")
        # Add sale-level metadata: descripcion (if not yet added), forma de pago, incluye diseño, total pagado
        try:
            # Descripcion from sale_info if not already printed
            if not any(l.startswith('DESCRIPCION:') for l in lines):
                sdesc = sale_info.get('descripcion') or ''
                if sdesc:
                    lines.append('-')
                    lines.append('DESCRIPCION:')
                    for l in _wrap_text(str(sdesc), 40):
                        lines.append(l)
            # Forma de pago
            if sale_info.get('forma_pago'):
                lines.append(f"FORMA PAGO: {sale_info.get('forma_pago')}")
            # Incluye diseno
            incluye_diseno = False
            if ('incluye_diseno' in details and details.get('incluye_diseno')) or (sale_info.get('diseno_usd', 0.0) > 0.0):
                incluye_diseno = True
            lines.append(f"INCLUYE DISEÑO: {'SI' if incluye_diseno else 'NO'}")
            # Total pagado: prefer ingresos_usd, then abono_usd, then venta_usd-restante
            paid = None
            if sale_info.get('ingresos_usd') and sale_info.get('ingresos_usd') > 0:
                paid = sale_info.get('ingresos_usd')
            elif sale_info.get('abono_usd') and sale_info.get('abono_usd') > 0:
                paid = sale_info.get('abono_usd')
            elif sale_info.get('venta_usd') is not None:
                paid = float(sale_info.get('venta_usd') or 0.0) - float(sale_info.get('restante') or 0.0)
            if paid is not None:
                lines.append(f"TOTAL PAGADO: $ {float(paid):.2f}")
        except Exception:
            pass
    else:
        # Fallback: plano con cualquier clave conocida
        for key in [
            "alto_mm", "ancho_mm", "material_nombre", "espesor_mm",
            "tipo_corte", "base_tipo", "base_color",
            "supports", "luz", "regulador", "light_box_enabled", "light_box_pct",
            "subtotal", "total"
        ]:
            if key in details:
                val = details.get(key)
                lines.append(f"{key}: {val}")
    # Guardar archivo
    out = _data_dir() / f"ORDER-{int(order_id):06d}.txt"
    out.write_text("\n".join(lines), encoding="utf-8")
    # Guardar JSON completo al lado
    (out.with_suffix('.json')).write_text(json.dumps(details, ensure_ascii=False, indent=2), encoding='utf-8')
    return out


def print_order_pdf(*, order_id: int, sale_id: int, product_name: str, status: str, details_json: str, customer: dict | None = None, out_path: Path | None = None) -> Path:
    """Genera un ticket PDF de 80 mm con diseño profesional tipo recibo/factura."""
    try:
        from reportlab.pdfgen import canvas
        from reportlab.lib.units import mm
        from reportlab.lib import colors
    except Exception:
        return print_order_80mm(order_id=order_id, sale_id=sale_id, product_name=product_name, status=status, details_json=details_json)

    out = Path(out_path) if out_path else (_data_dir() / f"ORDER-{int(order_id):06d}.pdf")

    try:
        details = json.loads(details_json or "{}")
    except Exception:
        details = {}

    items = details.get('items') if isinstance(details.get('items'), list) else []
    totals = details.get('totals') if isinstance(details.get('totals'), dict) else {}
    meta = details.get('meta') if isinstance(details.get('meta'), dict) else {}

    sale_info: dict[str, object] = {}
    customer_info: dict[str, str] = {}
    try:
        from .db import make_session_factory
        from .models import Sale, Customer

        SF = make_session_factory()
        with SF() as session:
            sale_obj = session.get(Sale, int(sale_id)) if sale_id else None
            if sale_obj:
                sale_info = {
                    'descripcion': getattr(sale_obj, 'descripcion', None),
                    'forma_pago': getattr(sale_obj, 'forma_pago', None),
                    'diseno_usd': _to_float(getattr(sale_obj, 'diseno_usd', 0.0)),
                    'ingresos_usd': _to_float(getattr(sale_obj, 'ingresos_usd', 0.0)),
                    'abono_usd': _to_float(getattr(sale_obj, 'abono_usd', 0.0)),
                    'venta_usd': _to_float(getattr(sale_obj, 'venta_usd', 0.0)),
                    'restante': _to_float(getattr(sale_obj, 'restante', 0.0)),
                    'total_bs': _to_float(getattr(sale_obj, 'total_bs', getattr(sale_obj, 'monto_bs', 0.0))),
                    'monto_bs': _to_float(getattr(sale_obj, 'monto_bs', 0.0)),
                    'tasa_bcv': _to_float(getattr(sale_obj, 'tasa_bcv', None), default=0.0),
                    'iva': _to_float(getattr(sale_obj, 'iva', 0.0)),
                    'fecha': getattr(sale_obj, 'fecha', None),
                    'fecha_pago': getattr(sale_obj, 'fecha_pago', None),
                    'asesor': getattr(sale_obj, 'asesor', None),
                    'numero_orden': getattr(sale_obj, 'numero_orden', None),
                    'cliente': getattr(sale_obj, 'cliente', None),
                    'cliente_id': getattr(sale_obj, 'cliente_id', None),
                    'notes': getattr(sale_obj, 'notes', None),
                }
                raw_cid = getattr(sale_obj, 'cliente_id', None)
                if raw_cid:
                    try:
                        cust_obj = session.get(Customer, int(raw_cid))
                    except Exception:
                        cust_obj = None
                    if cust_obj:
                        customer_info = {
                            'name': cust_obj.name or ((cust_obj.first_name or '') + ' ' + (cust_obj.last_name or '')).strip(),
                            'short_address': cust_obj.short_address or '',
                            'document': cust_obj.document or '',
                            'phone': cust_obj.phone or '',
                        }
    except Exception:
        sale_info = sale_info or {}

    # Priorizar customer recibido, luego meta, luego sale
    resolved_customer = {
        'name': '',
        'short_address': '',
        'document': '',
        'phone': '',
    }
    if isinstance(customer, dict):
        resolved_customer.update({k: str(customer.get(k) or '') for k in resolved_customer.keys()})

    if isinstance(meta.get('cliente'), dict):
        resolved_customer.update({k: str(meta['cliente'].get(k) or '') for k in resolved_customer.keys() if isinstance(meta['cliente'], dict)})
    elif isinstance(meta.get('cliente'), str) and not resolved_customer['name']:
        resolved_customer['name'] = str(meta.get('cliente'))

    if not resolved_customer['name'] and sale_info.get('cliente'):
        resolved_customer['name'] = str(sale_info.get('cliente') or '')

    # Merge customer info from DB last to avoid overwriting explicit data with empties
    for key, value in customer_info.items():
        if value and not resolved_customer.get(key):
            resolved_customer[key] = value

    # Complement metadata from meta keys if available
    for alias_key in ('documento', 'rif', 'rif_ci', 'identificacion'):
        if not resolved_customer['document'] and isinstance(meta.get(alias_key), str):
            resolved_customer['document'] = meta[alias_key]

    if not resolved_customer['short_address'] and isinstance(meta.get('direccion'), str):
        resolved_customer['short_address'] = meta.get('direccion') or ''

    if not resolved_customer['phone'] and isinstance(meta.get('telefono'), str):
        resolved_customer['phone'] = meta.get('telefono') or ''

    rate_bcv = _to_float(sale_info.get('tasa_bcv'), 0.0) or _to_float(meta.get('tasa_bcv'), 0.0)
    total_bs = _to_float(totals.get('total_bs'), 0.0)
    total_usd = _to_float(totals.get('total_usd'), 0.0)
    if total_bs == 0.0 and rate_bcv and total_usd:
        total_bs = total_usd * rate_bcv
    if total_bs == 0.0:
        total_bs = _to_float(sale_info.get('total_bs') or sale_info.get('monto_bs'), 0.0)

    diseno_usd = _to_float(sale_info.get('diseno_usd'), 0.0)
    diseno_bs = diseno_usd * rate_bcv if rate_bcv else 0.0
    if diseno_bs == 0.0:
        diseno_bs = _to_float(meta.get('diseno_bs'), 0.0)

    instalacion_bs = _to_float(meta.get('instalacion_bs') or meta.get('instalacion'), 0.0)
    iva_amount = _to_float(sale_info.get('iva'), 0.0)

    description_text = str(details.get('descripcion_text') or sale_info.get('descripcion') or product_name or '').strip()
    if not description_text and items:
        try:
            first_desc = items[0].get('descripcion') or items[0].get('label') or product_name
            description_text = str(first_desc)
        except Exception:
            pass

    description_lines: list[str] = []
    for raw_line in description_text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        description_lines.extend(_wrap_text(line, width=38))

    if not description_lines:
        description_lines.append(product_name or '—')

    # Preparar datos de items (descripcion, cantidad y subtotal en Bs)
    item_lines: list[tuple[str, float, float]] = []
    if items:
        for idx, item in enumerate(items, start=1):
            qty = _to_float(item.get('cantidad'), 0.0) or 0.0
            subtotal_bs = _to_float(item.get('subtotal_bs'), 0.0)
            if subtotal_bs == 0.0 and rate_bcv:
                subtotal_bs = _to_float(item.get('subtotal_usd'), 0.0) * rate_bcv
            if subtotal_bs == 0.0 and idx == 1 and total_bs:
                subtotal_bs = total_bs
            desc = str(item.get('descripcion') or item.get('label') or product_name or f'Item {idx}')
            item_lines.append((desc, qty, subtotal_bs))
    else:
        item_lines.append((product_name or 'Servicio', 1.0, total_bs or summary_amount))

    # Detectar desglose de pagos desde el payload/meta (mover después de item_lines para evitar referencias previas)
    payment_lines: list[tuple[str, str, float]] = []
    raw_payments = None
    for key in ('payment_breakdown', 'payments', 'metodos_pago'):
        if isinstance(meta.get(key), (list, dict)):
            raw_payments = meta.get(key)
            break
    if raw_payments:
        if isinstance(raw_payments, list):
            for entry in raw_payments:
                if not isinstance(entry, dict):
                    continue
                method = str(entry.get('method') or entry.get('metodo') or '')
                concept = str(entry.get('label') or entry.get('concepto') or method)
                amount_bs = _to_float(entry.get('amount_bs') or entry.get('monto_bs') or entry.get('monto'))
                payment_lines.append((method or concept, concept, amount_bs))
        elif isinstance(raw_payments, dict):
            for method, entry in raw_payments.items():
                if isinstance(entry, dict):
                    concept = str(entry.get('label') or entry.get('concepto') or method)
                    amount_bs = _to_float(entry.get('amount_bs') or entry.get('monto_bs') or entry.get('monto'))
                else:
                    concept = str(method)
                    amount_bs = _to_float(entry)
                payment_lines.append((str(method), concept, amount_bs))

    if not payment_lines:
        primary_method = str(sale_info.get('forma_pago') or meta.get('forma_pago') or 'Efectivo$')
        payment_lines = [
            (primary_method, 'Total Venta', total_bs),
            ('Zelle$', 'Diseño', diseno_bs),
            ('Pago Móvil', 'Instalación', instalacion_bs),
            ('Punto Venta', 'I.V.A 16%', iva_amount),
        ]

    # Calcular totales derivados tras conocer item_lines
    summary_amount = sum(amount for _, _, amount in payment_lines if amount)
    items_total_bs = sum(amount for _, _, amount in item_lines)
    total_bs_display = total_bs or summary_amount

    # Resolver códigos visibles
    order_code = str(meta.get('order_number') or meta.get('numero_orden') or f"ORD-{int(order_id):06d}")
    order_digits = ''.join(ch for ch in order_code if ch.isdigit()) or f"{int(order_id):06d}"
    try:
        from .repository import get_sale_display_number
        sale_display = get_sale_display_number(int(sale_id), payment_date=sale_info.get('fecha_pago')) if sale_id else ''
    except Exception:
        sale_display = f"V-{int(sale_id):06d}" if sale_id else ''

    entrega_label = ''
    for key in ('fecha_entrega', 'delivery_date', 'entrega'):
        if meta.get(key):
            entrega_label = str(meta.get(key))
            break
    if not entrega_label:
        entrega_label = 'N/A'

    asesor_label = str(sale_info.get('asesor') or meta.get('asesor') or '').strip()
    if not asesor_label and resolved_customer['name']:
        asesor_label = resolved_customer['name']

    emission_time = datetime.now().strftime('%H:%M:%S')

    # --- Diseño profesional tipo recibo/factura ---
    page_height = 280 * mm  # Aumentado para mejor espaciado
    width = 80 * mm
    c = canvas.Canvas(str(out), pagesize=(width, page_height))
    
    # Márgenes y espaciado
    margin_x = 5 * mm
    margin_y = 5 * mm
    line_h = 4.5 * mm
    y = page_height - margin_y

    def draw_centered(text: str, y_pos: float, font: str = 'Helvetica', size: int = 9, bold: bool = False) -> float:
        """Dibuja texto centrado y retorna nueva posición Y."""
        font_name = f'{font}-Bold' if bold else font
        c.setFont(font_name, size)
        c.drawCentredString(width / 2, y_pos, text)
        return y_pos - line_h

    def draw_left(text: str, y_pos: float, x_pos: float = None, font: str = 'Helvetica', size: int = 8, bold: bool = False) -> float:
        """Dibuja texto alineado a la izquierda."""
        font_name = f'{font}-Bold' if bold else font
        c.setFont(font_name, size)
        c.drawString(x_pos if x_pos is not None else margin_x, y_pos, text)
        return y_pos - line_h

    def draw_right(text: str, y_pos: float, font: str = 'Helvetica', size: int = 8, bold: bool = False) -> float:
        """Dibuja texto alineado a la derecha."""
        font_name = f'{font}-Bold' if bold else font
        c.setFont(font_name, size)
        c.drawRightString(width - margin_x, y_pos, text)
        return y_pos - line_h

    def draw_line_separator(y_pos: float, style: str = 'solid') -> float:
        """Dibuja línea separadora horizontal."""
        c.setLineWidth(0.5 if style == 'solid' else 0.3)
        if style == 'dashed':
            c.setDash(2, 2)
        c.line(margin_x, y_pos, width - margin_x, y_pos)
        c.setDash()  # Reset
        return y_pos - line_h * 0.5

    def draw_box(x: float, y: float, w: float, h: float, fill_color: tuple = None) -> None:
        """Dibuja un cuadro con borde opcional."""
        if fill_color:
            c.setFillColorRGB(*fill_color)
            c.rect(x, y, w, h, fill=1)
            c.setFillColorRGB(0, 0, 0)  # Reset a negro
        else:
            c.setLineWidth(0.5)
            c.rect(x, y, w, h, fill=0)

    # ============================================================
    # ENCABEZADO EMPRESA
    # ============================================================
    # Logo placeholder - si existe logo, se puede agregar aquí
    # logo_path = Path(__file__).parent.parent.parent / 'assets' / 'img' / 'logo.png'
    # if logo_path.exists():
    #     c.drawImage(str(logo_path), margin_x, y - 15*mm, width=15*mm, height=15*mm, preserveAspectRatio=True)
    #     y -= 16*mm
    
    y = draw_centered('MR.7 PUBLICIDAD, C.A.', y, size=13, bold=True)
    y = draw_centered('RIF: J-506410990', y, size=8)
    y = draw_centered('Av. Universidad, Centro Parque Carabobo', y, size=7)
    y = draw_centered('Torre A, Piso 4, Ofic 413', y, size=7)
    y = draw_centered('Tel: (0241) 000-0000', y, size=7)
    y -= line_h * 0.4
    
    # Línea separadora doble para destacar
    c.setLineWidth(1.5)
    c.line(margin_x, y, width - margin_x, y)
    y -= 1.5
    c.setLineWidth(0.5)
    c.line(margin_x, y, width - margin_x, y)
    y -= line_h * 0.5

    # ============================================================
    # TÍTULO FACTURA/RECIBO
    # ============================================================
    # Cuadro destacado para el título
    title_box_y = y - line_h * 1.2
    draw_box(margin_x + 10, title_box_y, width - 2*margin_x - 20, line_h * 1.5, fill_color=(0.2, 0.2, 0.2))
    c.setFillColorRGB(1, 1, 1)  # Texto blanco
    c.setFont('Helvetica-Bold', 14)
    c.drawCentredString(width / 2, title_box_y + line_h * 0.4, 'FACTURA')
    c.setFillColorRGB(0, 0, 0)  # Reset a negro
    
    y = title_box_y - line_h * 0.5

    # ============================================================
    # BLOQUE DE INFORMACIÓN: ORDEN Y VENTA
    # ============================================================
    # Fondo gris claro con borde para destacar
    box_y = y - line_h * 3.5
    c.setLineWidth(0.8)
    c.setStrokeColorRGB(0.6, 0.6, 0.6)
    draw_box(margin_x, box_y, width - 2*margin_x, line_h * 4, fill_color=(0.94, 0.94, 0.94))
    c.setStrokeColorRGB(0, 0, 0)  # Reset
    
    info_x = margin_x + 3
    c.setFont('Helvetica-Bold', 7)
    c.drawString(info_x, y - 4, 'No. Orden:')
    c.setFont('Helvetica-Bold', 11)
    c.drawString(info_x + 20, y - 4, order_digits.zfill(6))
    
    c.setFont('Helvetica-Bold', 7)
    c.drawString(info_x, y - 11.5, 'No. Venta:')
    c.setFont('Helvetica', 9)
    c.drawString(info_x + 20, y - 11.5, sale_display or f'V-{int(sale_id):06d}' if sale_id else '—')
    
    c.setFont('Helvetica-Bold', 7)
    c.drawString(info_x, y - 18.5, 'Fecha:')
    c.setFont('Helvetica', 8)
    c.drawString(info_x + 20, y - 18.5, f'{datetime.now().strftime("%d/%m/%Y")} {emission_time}')
    
    if entrega_label and entrega_label != 'N/A':
        c.setFont('Helvetica-Bold', 7)
        c.drawString(info_x, y - 25.5, 'Entrega:')
        c.setFont('Helvetica', 8)
        c.drawString(info_x + 20, y - 25.5, entrega_label[:25])
    
    y = box_y - line_h * 0.8

    # ============================================================
    # DATOS DEL CLIENTE
    # ============================================================
    y = draw_line_separator(y, 'dashed')
    y -= line_h * 0.3
    y = draw_left('DATOS DEL CLIENTE', y, bold=True, size=9)
    y -= line_h * 0.1
    
    client_name = resolved_customer.get('name') or '—'
    y = draw_left(f'Nombre: {client_name[:35]}', y, size=8)
    
    client_doc = resolved_customer.get('document') or '—'
    y = draw_left(f'RIF/CI: {client_doc}', y, size=8)
    
    client_addr = resolved_customer.get('short_address') or '—'
    if len(client_addr) > 38:
        y = draw_left(f'Dirección: {client_addr[:38]}', y, size=7)
        y = draw_left(f'           {client_addr[38:76]}', y, size=7)
    else:
        y = draw_left(f'Dirección: {client_addr}', y, size=8)
    
    client_phone = resolved_customer.get('phone') or meta.get('telefono_contacto') or '—'
    y = draw_left(f'Teléfono: {client_phone}', y, size=8)
    
    y -= line_h * 0.3

    # ============================================================
    # DETALLE DE PRODUCTOS/SERVICIOS
    # ============================================================
    y = draw_line_separator(y, 'solid')
    y -= line_h * 0.3
    y = draw_centered('DETALLE DE PRODUCTOS/SERVICIOS', y, bold=True, size=9)
    y -= line_h * 0.5
    
    # Encabezados de tabla
    c.setFont('Helvetica-Bold', 8)
    col_cant = margin_x + 2
    col_desc = margin_x + 12
    col_precio = width - margin_x - 24
    col_total = width - margin_x - 2
    
    c.drawString(col_cant, y, 'Cant')
    c.drawString(col_desc, y, 'Descripción')
    c.drawRightString(col_precio, y, 'P.Unit Bs')
    c.drawRightString(col_total, y, 'Total Bs')
    y -= line_h * 0.8
    
    # Línea bajo encabezados
    c.setLineWidth(0.5)
    c.line(margin_x, y + 2, width - margin_x, y + 2)
    y -= line_h * 0.3
    
    # Items
    c.setFont('Helvetica', 8)
    for desc, qty, amount in item_lines:
        qty_str = f"{int(qty)}" if abs(qty - int(qty)) < 1e-6 else f"{qty:.1f}"
        c.drawString(col_cant, y, qty_str.rjust(3))
        
        # Descripción con word wrap si es muy larga
        if len(desc) > 22:
            c.drawString(col_desc, y, desc[:22])
            y -= line_h * 0.7
            c.setFont('Helvetica', 7)
            c.drawString(col_desc, y, desc[22:44])
            c.setFont('Helvetica', 8)
        else:
            c.drawString(col_desc, y, desc)
        
        unit_bs = amount / qty if qty else 0.0
        c.drawRightString(col_precio, y, _format_bs(unit_bs))
        c.drawRightString(col_total, y, _format_bs(amount))
        y -= line_h
    
    y += line_h * 0.3
    c.setLineWidth(0.5)
    c.line(margin_x, y, width - margin_x, y)
    y -= line_h * 0.8

    # ============================================================
    # SECCIÓN DE TOTALES
    # ============================================================
    # Fondo destacado con borde
    totals_box_y = y - line_h * 6.2
    c.setLineWidth(1)
    c.setStrokeColorRGB(0.3, 0.3, 0.3)
    draw_box(margin_x, totals_box_y, width - 2*margin_x, line_h * 6.8, fill_color=(0.96, 0.96, 0.96))
    c.setStrokeColorRGB(0, 0, 0)  # Reset
    
    c.setFont('Helvetica', 9)
    label_x = margin_x + 5
    value_x = width - margin_x - 3
    
    c.drawString(label_x, y, 'Subtotal Bs:')
    c.drawRightString(value_x, y, _format_bs(items_total_bs))
    y -= line_h
    
    if diseno_bs > 0:
        c.drawString(label_x, y, 'Diseño Bs:')
        c.drawRightString(value_x, y, _format_bs(diseno_bs))
        y -= line_h
    
    if instalacion_bs > 0:
        c.drawString(label_x, y, 'Instalación Bs:')
        c.drawRightString(value_x, y, _format_bs(instalacion_bs))
        y -= line_h
    
    if iva_amount > 0:
        c.drawString(label_x, y, 'I.V.A. (16%) Bs:')
        c.drawRightString(value_x, y, _format_bs(iva_amount))
        y -= line_h
    
    # Línea separadora antes del total
    y -= line_h * 0.1
    c.setLineWidth(0.8)
    c.line(margin_x + 3, y, width - margin_x - 3, y)
    y -= line_h * 0.6
    
    # Total destacado con fondo oscuro
    total_highlight_y = y - line_h * 0.1
    draw_box(margin_x + 2, total_highlight_y - 3, width - 2*margin_x - 4, line_h * 2.3, fill_color=(0.15, 0.15, 0.15))
    
    c.setFillColorRGB(1, 1, 1)  # Texto blanco
    c.setFont('Helvetica-Bold', 11)
    c.drawString(label_x, y, 'TOTAL Bs:')
    c.drawRightString(value_x, y, _format_bs(total_bs_display))
    y -= line_h
    
    c.setFont('Helvetica-Bold', 10)
    c.drawString(label_x, y, 'TOTAL USD:')
    c.drawRightString(value_x, y, f'$ {total_usd:.2f}')
    c.setFillColorRGB(0, 0, 0)  # Reset a negro
    
    y = totals_box_y - line_h * 0.8

    # ============================================================
    # MÉTODOS DE PAGO
    # ============================================================
    y = draw_line_separator(y, 'dashed')
    y -= line_h * 0.3
    y = draw_left('MÉTODOS DE PAGO', y, bold=True, size=9)
    y -= line_h * 0.2
    
    c.setFont('Helvetica', 8)
    for method, concept, amount in payment_lines:
        if amount > 0:
            line_text = f'{method} - {concept}: {_format_bs(amount)}'
            y = draw_left(line_text[:45], y, size=8)
    
    y -= line_h * 0.3

    # ============================================================
    # OBSERVACIONES
    # ============================================================
    if description_lines:
        y = draw_line_separator(y, 'dashed')
        y -= line_h * 0.3
        y = draw_left('OBSERVACIONES', y, bold=True, size=9)
        y -= line_h * 0.2
        
        c.setFont('Helvetica', 7)
        for line in description_lines[:4]:  # Máximo 4 líneas
            y = draw_left(line[:50], y, size=7)
        
        y -= line_h * 0.3

    # ============================================================
    # PIE DE PÁGINA - TÉRMINOS Y CONDICIONES
    # ============================================================
    y = draw_line_separator(y, 'solid')
    y -= line_h * 0.3
    
    # Fondo claro para términos
    terms_y = y - line_h * 3.5
    draw_box(margin_x, terms_y, width - 2*margin_x, line_h * 4, fill_color=(0.98, 0.98, 0.98))
    
    c.setFont('Helvetica', 6)
    footer_lines = [
        '• Estimado Cliente: Verifique su pedido antes de retirarse.',
        '• No se realizan devoluciones por compras erróneas.',
        '• Documento sin validez fiscal. Precios no incluyen I.V.A.',
        '• Exija su factura fiscal.',
    ]
    
    for line in footer_lines:
        y = draw_centered(line, y, size=6)
    
    y = terms_y - line_h * 0.8
    
    # Separador con línea punteada
    c.setDash(1, 2)
    c.setLineWidth(0.3)
    c.line(margin_x + 10, y, width - margin_x - 10, y)
    c.setDash()  # Reset
    y -= line_h * 0.5
    
    # Info del asesor y hora
    if asesor_label:
        c.setFont('Helvetica-Bold', 7)
        y = draw_centered(f'Atendido por: {asesor_label}', y, size=7, bold=True)
    
    c.setFont('Helvetica', 6)
    y = draw_centered(f'Emisión: {datetime.now().strftime("%d/%m/%Y")} a las {emission_time}', y, size=6)
    
    # Mensaje de agradecimiento
    y -= line_h * 0.5
    c.setFont('Helvetica-Bold', 9)
    y = draw_centered('¡GRACIAS POR SU PREFERENCIA!', y, size=9, bold=True)
    
    # Marco decorativo inferior
    y -= line_h * 0.3
    c.setLineWidth(2)
    c.line(margin_x, margin_y + 3, width - margin_x, margin_y + 3)
    c.setLineWidth(0.5)
    c.line(margin_x, margin_y + 1, width - margin_x, margin_y + 1)

    # Guardar PDF
    c.save()
    (out.with_suffix('.json')).write_text(json.dumps(details, ensure_ascii=False, indent=2), encoding='utf-8')
    return out
