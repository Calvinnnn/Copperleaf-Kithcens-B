import chromadb

from sentence_transformers import SentenceTransformer


MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
COLLECTION_NAME = "copperleaf_documents"
DB_PATH = "rag/chroma_db"


def retrieve(query: str, top_k: int = 5):
    """
    Retrieve the most relevant document chunks for a user query.
    """

    model = SentenceTransformer(MODEL_NAME)

    query_embedding = model.encode(
        [query],
        normalize_embeddings=True
    )[0].tolist()

    client = chromadb.PersistentClient(path=DB_PATH)

    collection = client.get_collection(
        name=COLLECTION_NAME
    )

    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=top_k
    )

    retrieved_chunks = []

    for i in range(len(results["documents"][0])):
        retrieved_chunks.append({
            "text": results["documents"][0][i],
            "metadata": results["metadatas"][0][i],
            "distance": results["distances"][0][i]
        })

    return retrieved_chunks


if __name__ == "__main__":

    query = input("Enter your question: ")

    results = retrieve(query)

    print("\nRetrieved chunks:\n")

    for index, result in enumerate(results, start=1):
        print(f"--- Result {index} ---")
        print(f"Source: {result['metadata']['source']}")
        print(f"Page: {result['metadata']['page']}")
        print(f"Distance: {result['distance']:.4f}")
        print(result["text"])
        print()