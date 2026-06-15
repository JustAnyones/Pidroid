import pathlib
import timeit

import chromadb
from PIL import Image

from pidroid_ai.embed import embed_image, load_model

EXTENSION_GLOBS = ["**/*.png", "**/*.jpeg", "**/*.jpg"]

PROJECT_ROOT = pathlib.Path(__file__).parent.parent.parent
KNOWN_SCAM_IMAGES_DIR = PROJECT_ROOT / "pidroid-bot" / "src" / "pidroid" / "resources" / "scam_images"

def main() -> None:
    # Load the embedding model
    model = load_model()

    # Connect to chromadb
    client = chromadb.EphemeralClient()
    collection = client.create_collection(
        name="vectors",
        metadata={"hnsw:space": "cosine"},
    )

    # Embed all known scam images
    scam_images = [f for ext in EXTENSION_GLOBS for f in KNOWN_SCAM_IMAGES_DIR.glob(ext)]
    vec = None
    for i, image_path in enumerate(scam_images):
        start_time = timeit.default_timer()
        with Image.open(image_path) as img:
            embedding = embed_image(model, img)
            collection.add(
                documents=[str(image_path)],
                embeddings=[embedding],
                ids=[str(i)],
            )
            end_time = timeit.default_timer()
            vec = embedding
            print(f"Embedding image: {image_path}, Time taken: {end_time - start_time:.4f} seconds")

    results = collection.query(
        query_embeddings=[vec],
        n_results=5,
    )
    print("Query results:", results)

if __name__ == "__main__":
    main()
