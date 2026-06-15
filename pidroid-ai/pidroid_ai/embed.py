from PIL import Image
from sentence_transformers import SentenceTransformer


def load_model() -> SentenceTransformer:
    return SentenceTransformer("google/siglip-base-patch16-224")
    return SentenceTransformer("facebook/dino-vits16") # sucks
    return SentenceTransformer("clip-ViT-B-32")

def embed_image(model: SentenceTransformer, image: Image.Image) -> list[float]:
    return model.encode(image).tolist()
