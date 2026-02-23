import pytest
import os
from PIL import Image
import io
from app.utils import generate_image_icon, convert_to_webp

def test_image_upload_processing(authenticated_client, app):
    """
    Test that uploading an image:
    1. Resizes original if > 2048 height.
    2. Generates _icon with 200 height.
    3. Generates _big with 600 height.
    """
    # Create a dummy large image (e.g. 1000x3000)
    large_img = Image.new('RGB', (1000, 3000), color='red')
    img_io = io.BytesIO()
    large_img.save(img_io, 'PNG')
    img_io.seek(0)

    data = {
        'file': (img_io, 'large_test_image.png')
    }

    response = authenticated_client.post('/api/admin/upload-image', data=data, content_type='multipart/form-data')
    assert response.status_code == 201

    json_data = response.get_json()
    url = json_data['url'] # e.g. /static/uploads/products/uuid_large_test_image.webp

    # Check paths
    # URL is relative to root, but file system path is app.root_path + ...
    # url starts with /static/
    filename = url.split('/')[-1]
    base_path = os.path.join(app.root_path, 'static', 'uploads', 'products')

    original_path = os.path.join(base_path, filename)
    icon_path = os.path.join(base_path, filename.replace('.webp', '_icon.webp'))
    big_path = os.path.join(base_path, filename.replace('.webp', '_big.webp'))

    print(f"Checking paths:\nOriginal: {original_path}\nIcon: {icon_path}\nBig: {big_path}")

    if not os.path.exists(big_path):
        print("Big file missing. Listing dir:")
        print(os.listdir(base_path))

    assert os.path.exists(original_path), "Original file should exist"
    assert os.path.exists(icon_path), "Icon file should exist"
    assert os.path.exists(big_path), "Big file should exist"

    # Check Dimensions
    with Image.open(original_path) as img:
        print(f"Original Size: {img.size}")
        assert img.height == 2048, f"Original height should be 2048, got {img.height}"
        # Width should be 1000 * (2048/3000) ~= 682
        assert 680 <= img.width <= 685

    with Image.open(icon_path) as img:
        print(f"Icon Size: {img.size}")
        assert img.height == 200, f"Icon height should be 200, got {img.height}"

    with Image.open(big_path) as img:
        print(f"Big Size: {img.size}")
        assert img.height == 600, f"Big height should be 600, got {img.height}"

def test_image_upload_small_no_resize(authenticated_client, app):
    """
    Test that uploading a small image (height < 2048) keeps original height.
    """
    small_img = Image.new('RGB', (500, 1000), color='blue')
    img_io = io.BytesIO()
    small_img.save(img_io, 'JPEG')
    img_io.seek(0)

    data = {
        'file': (img_io, 'small_test.jpg')
    }

    response = authenticated_client.post('/api/admin/upload-image', data=data, content_type='multipart/form-data')
    assert response.status_code == 201

    url = response.get_json()['url']
    filename = url.split('/')[-1]
    base_path = os.path.join(app.root_path, 'static', 'uploads', 'products')
    original_path = os.path.join(base_path, filename)

    with Image.open(original_path) as img:
        assert img.height == 1000, f"Small image height should remain 1000, got {img.height}"
