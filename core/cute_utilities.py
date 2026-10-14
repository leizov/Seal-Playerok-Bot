import paths
import os
import random

CUTE_TEXTS = []
def get_random_cute_png_path():
    """
    Возвращает путь к случайной милой PNG картинке.
    """
    if not os.path.isdir(paths.RANDOM_CUTE_IMAGES_DIR):
        return None
    png_files = [
        f for f in os.listdir(paths.RANDOM_CUTE_IMAGES_DIR) 
        if f.lower().endswith('.png') 
        or f.lower().endswith('.jpg') 
        or f.lower().endswith('.jpeg')
    ]
    if not png_files:
        return None
    random_file = random.choice(png_files)
    return os.path.join(paths.RANDOM_CUTE_IMAGES_DIR, random_file)

def get_random_cute_text():
    """
    Возвращает случайный милый текст.
    """
    
    return random.choice(CUTE_TEXTS)

