from sentence_transformers import SentenceTransformer

def load_model(
    model = "intfloat/multilingual-e5-small",
    device = "cpu"
) -> SentenceTransformer:
    return SentenceTransformer(model, device = device)

def prepare_description(description: str | None) -> str | None:
    text = " ".join((description or "").split())
    return text or None

def embed_description(model: SentenceTransformer, description: str | None) -> list[float] | None:
    if description is None or not description.strip():
        return None

    description = prepare_description(description)

    vector = model.encode(
        f"query: {description.strip()}",
        normalize_embeddings = True
    )

    return vector.tolist()

if __name__ == "__main__":
    model = load_model()
    print(embed_description(model, "This is a coffee store"))