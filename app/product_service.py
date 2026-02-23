import csv
import json
import io
from .models import Product, Variant, ProductImage, VariantImage
from .extensions import db
from .utils import ensure_icon_for_url
from flask import current_app

def products_to_csv(products):
    if not products:
        return ""
    fieldnames = [
        "product_sku", "name", "category", "base_price_cents",
        "description", "short_description", "product_details",
        "tag1", "tag2", "tag3", "weight_grams", "message", "status",
        "related_products_json", "proposed_products_json", "dimensions_json",
        "variants_json", "images_json"
    ]
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    for p in products:
        row = {
            "product_sku": p.get("product_sku"),
            "name": p.get("name"),
            "category": p.get("category"),
            "base_price_cents": p.get("base_price_cents"),
            "description": p.get("description"),
            "short_description": p.get("short_description"),
            "product_details": p.get("product_details"),
            "tag1": p.get("tag1"),
            "tag2": p.get("tag2"),
            "tag3": p.get("tag3"),
            "weight_grams": p.get("weight_grams"),
            "message": p.get("message"),
            "status": p.get("status"),
            "related_products_json": json.dumps(p.get("related_products") or []),
            "proposed_products_json": json.dumps(p.get("proposed_products") or []),
            "dimensions_json": json.dumps(p.get("dimensions_json") or {}),
            "variants_json": json.dumps(p.get("variants") or []),
            "images_json": json.dumps(p.get("images") or [])
        }
        writer.writerow(row)
    return output.getvalue()

def parse_products_file(file_storage, file_ext):
    content = file_storage.read().decode('utf-8')
    if file_ext == 'json':
        return json.loads(content)
    elif file_ext == 'csv':
        reader = csv.DictReader(io.StringIO(content))
        products = []
        for row in reader:
            p = {
                "product_sku": row.get("product_sku"),
                "name": row.get("name"),
                "category": row.get("category"),
                "base_price_cents": int(row.get("base_price_cents") or 0),
                "description": row.get("description"),
                "short_description": row.get("short_description"),
                "product_details": row.get("product_details"),
                "tag1": row.get("tag1"),
                "tag2": row.get("tag2"),
                "tag3": row.get("tag3"),
                "weight_grams": int(row.get("weight_grams") or 0) if row.get("weight_grams") else None,
                "message": row.get("message"),
                "status": row.get("status"),
                "related_products": json.loads(row.get("related_products_json") or "[]"),
                "proposed_products": json.loads(row.get("proposed_products_json") or "[]"),
                "dimensions_json": json.loads(row.get("dimensions_json") or "{}"),
                "variants": json.loads(row.get("variants_json") or "[]"),
                "images": json.loads(row.get("images_json") or "[]")
            }
            products.append(p)
        return products
    else:
        raise ValueError("Unsupported file format")

def _create_product_internal(data):
    if not data.get('product_sku'): return
    # Sanitize SKU: No spaces allowed
    p_sku = str(data['product_sku']).strip().replace(" ", "_")

    product = Product(
        product_sku=p_sku,
        name=data.get('name', 'Unknown'),
        description=data.get('description'),
        short_description=data.get('short_description'),
        product_details=data.get('product_details'),
        related_products=data.get('related_products'),
        proposed_products=data.get('proposed_products'),
        tag1=data.get('tag1'),
        tag2=data.get('tag2'),
        tag3=data.get('tag3'),
        category=data.get('category'),
        base_price_cents=int(data.get('base_price_cents') or 0),
        weight_grams=data.get('weight_grams'),
        dimensions_json=data.get('dimensions_json'),
        message=data.get('message'),
        status=data.get('status', 'draft')
    )

    # Sync is_active with status
    product.is_active = (product.status == 'published')

    db.session.add(product)
    db.session.flush()

    for idx, img in enumerate(data.get('images', [])):
        url = img.get('url') if isinstance(img, dict) else str(img)
        alt = img.get('alt_text') if isinstance(img, dict) else ''
        order = int(img.get('display_order', img.get('order', idx)) if isinstance(img, dict) else idx)
        ensure_icon_for_url(url, current_app.root_path)
        pimg = ProductImage(product_id=product.id, url=url, alt_text=alt, display_order=order)
        db.session.add(pimg)

    for v_data in data.get('variants', []):
        sku = v_data.get('sku')
        if not sku: continue
        # Sanitize Variant SKU
        sku = str(sku).strip().replace(" ", "_")

        variant = Variant(
            product_id=product.id,
            sku=sku,
            color_name=v_data.get('color_name'),
            size=v_data.get('size'),
            stock_quantity=int(v_data.get('stock_quantity') or 0),
            price_modifier_cents=int(v_data.get('price_modifier_cents') or 0)
        )
        db.session.add(variant)
        db.session.flush()
        for idx, vimg in enumerate(v_data.get('images', []) or []):
            vurl = vimg.get('url') if isinstance(vimg, dict) else str(vimg)
            valt = vimg.get('alt_text') if isinstance(vimg, dict) else ''
            vorder = int(vimg.get('display_order', vimg.get('order', idx)) if isinstance(vimg, dict) else idx)
            ensure_icon_for_url(vurl, current_app.root_path)
            vi = VariantImage(variant_id=variant.id, url=vurl, alt_text=valt, display_order=vorder)
            db.session.add(vi)

def _update_product_internal(product, data):
    product.name = data.get('name', product.name)
    product.description = data.get('description', product.description)
    product.short_description = data.get('short_description', product.short_description)
    product.product_details = data.get('product_details', product.product_details)
    product.related_products = data.get('related_products', product.related_products)
    product.proposed_products = data.get('proposed_products', product.proposed_products)
    product.tag1 = data.get('tag1', product.tag1)
    product.tag2 = data.get('tag2', product.tag2)
    product.tag3 = data.get('tag3', product.tag3)
    product.category = data.get('category', product.category)
    product.base_price_cents = int(data.get('base_price_cents', product.base_price_cents or 0))
    product.weight_grams = data.get('weight_grams', product.weight_grams)
    product.dimensions_json = data.get('dimensions_json', product.dimensions_json)
    product.message = data.get('message', product.message)

    if 'status' in data:
        product.status = data.get('status')
        # Sync is_active
        product.is_active = (product.status == 'published')
    elif 'is_active' in data:
        # Fallback for backward compatibility if status not sent but is_active is
        # Though ideally we move to status fully.
        product.is_active = bool(data.get('is_active'))
        if product.is_active:
            product.status = 'published'
        elif product.status == 'published':
            product.status = 'draft'

    # Replace Images
    ProductImage.query.filter_by(product_id=product.id).delete()
    for idx, img in enumerate(data.get('images', [])):
        url = img.get('url') if isinstance(img, dict) else str(img)
        alt = img.get('alt_text') if isinstance(img, dict) else ''
        order = int(img.get('display_order', img.get('order', idx)) if isinstance(img, dict) else idx)
        ensure_icon_for_url(url, current_app.root_path)
        pimg = ProductImage(product_id=product.id, url=url, alt_text=alt, display_order=order)
        db.session.add(pimg)

    # Replace Variants: Explicit Delete to ensure clean state
    # First, delete all VariantImages associated with these variants
    # Subquery for variant IDs to delete
    variant_ids_q = db.session.query(Variant.id).filter(Variant.product_id == product.id)
    VariantImage.query.filter(VariantImage.variant_id.in_(variant_ids_q)).delete(synchronize_session=False)

    # Then delete the variants themselves
    Variant.query.filter(Variant.product_id == product.id).delete(synchronize_session=False)

    # Expire relationship to ensure it reloads empty
    db.session.expire(product, ['variants'])

    db.session.flush()

    for v_data in data.get('variants', []):
        sku = v_data.get('sku')
        if not sku: continue
        # Sanitize Variant SKU
        sku = str(sku).strip().replace(" ", "_")

        variant = Variant(
            product_id=product.id,
            sku=sku,
            color_name=v_data.get('color_name'),
            size=v_data.get('size'),
            stock_quantity=int(v_data.get('stock_quantity') or 0),
            price_modifier_cents=int(v_data.get('price_modifier_cents') or 0)
        )
        db.session.add(variant)
        db.session.flush()

        for idx, vimg in enumerate(v_data.get('images', []) or []):
            vurl = vimg.get('url') if isinstance(vimg, dict) else str(vimg)
            valt = vimg.get('alt_text') if isinstance(vimg, dict) else ''
            vorder = int(vimg.get('display_order', vimg.get('order', idx)) if isinstance(vimg, dict) else idx)
            ensure_icon_for_url(vurl, current_app.root_path)
            vi = VariantImage(variant_id=variant.id, url=vurl, alt_text=valt, display_order=vorder)
            db.session.add(vi)
