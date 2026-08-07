import chromadb

from rag.chunking import create_chunks
from rag.embeddings import create_embeddings


COLLECTION_NAME = "copperleaf_documents"
DB_PATH = "rag/chroma_db"


def create_vector_store():
    """
    Create a persistent ChromaDB collection and store
    document chunks together with their embeddings and metadata.
    """

    print("Loading documents and creating chunks...")

    chunks = create_chunks()

    print(f"Total chunks: {len(chunks)}")

    print("Creating embeddings...")

    embeddings = create_embeddings(chunks)

    print("Connecting to ChromaDB...")

    client = chromadb.PersistentClient(path=DB_PATH)

    collection = client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={
            "description": "Copperleaf Kitchens RAG knowledge base"
        }
    )

    ids = []
    documents = []
    metadatas = []
    vectors = []

    for index, (chunk, embedding) in enumerate(
        zip(chunks, embeddings)
    ):
        ids.append(f"chunk_{index}")

        documents.append(chunk["text"])

        metadatas.append({
            "source": chunk["metadata"]["source"],
            "page": chunk["metadata"]["page"],
            "chunk_id": chunk["metadata"]["chunk_id"]
        })

        vectors.append(embedding.tolist())

    collection.upsert(
        ids=ids,
        documents=documents,
        metadatas=metadatas,
        embeddings=vectors
    )

    print()
    print("Vector store created successfully!")
    print(f"Collection: {COLLECTION_NAME}")
    print(f"Documents stored: {collection.count()}")


if __name__ == "__main__":
    create_vector_store()