import json
from pathlib import Path
from qdrant_client import QdrantClient
from qdrant_client.models import (
    PointStruct, 
    VectorParams, 
    Distance, 
    SparseVectorParams
)
from fastembed import TextEmbedding, SparseTextEmbedding

class FaqIngestionPipeline:
    def __init__(self, collection_name: str, batch_size: int = 20):
        self.collection_name = collection_name
        self.batch_size = batch_size
        self.client = QdrantClient(url="http://localhost:6333")
        
        print("Carregando modelos de embedding...")
        self.dense_model = TextEmbedding(model_name="sentence-transformers/paraphrase-multilingual-mpnet-base-v2")
        self.sparse_model = SparseTextEmbedding(model_name="Qdrant/bm25")
        
    def setup_collection(self):
        if self.client.collection_exists(self.collection_name):
            print(f"A coleção '{self.collection_name}' já existe. Ignorando criação.")
            return

        print(f"Criando coleção '{self.collection_name}'...")
        self.client.create_collection(
            collection_name=self.collection_name,
            vectors_config={
                "dense": VectorParams(
                    size=768,
                    distance=Distance.COSINE
                )
            },
            sparse_vectors_config={
                "sparse": SparseVectorParams()
            }
        )

    # Note que agora esperamos que file_path seja um objeto Path ou string
    def process_and_ingest(self, file_path):
        with open(file_path, "r", encoding="utf-8") as f:
            faq_data = json.load(f)

        total_items = len(faq_data)
        print(f"Iniciando ingestão de {total_items} documentos em batches de {self.batch_size}...")

        for i in range(0, total_items, self.batch_size):
            batch = faq_data[i : i + self.batch_size]
            
            combined_texts = [f"{item['question']} {item['answer']}" for item in batch]
            
            dense_embeddings = list(self.dense_model.embed(combined_texts))
            sparse_embeddings = list(self.sparse_model.embed(combined_texts))
            
            points = []
            for j, item in enumerate(batch):
                point = PointStruct(
                    id=item["id"],
                    vectors={
                        "dense": dense_embeddings[j].tolist(),
                        "sparse": {
                            "indices": sparse_embeddings[j].indices.tolist(),
                            "values": sparse_embeddings[j].values.tolist()
                        }
                    },
                    payload={
                        "survey": item["survey"], 
                        "section": item["section"],
                        "question": item["question"],
                        "answer": item["answer"]
                    }
                )
                points.append(point)
            
            self.client.upsert(
                collection_name=self.collection_name,
                points=points
            )
            print(f"Batch {i // self.batch_size + 1} processado ({len(batch)} itens inseridos).")

        print("Ingestão concluída com sucesso!")

# --- Execução do Pipeline ---
if __name__ == "__main__":
    # --- Configuração de Caminhos Relativos com pathlib ---
    current_dir = Path(__file__).resolve().parent
    project_root = current_dir.parent.parent 
    data_dir = project_root / "data"
    input_filepath = data_dir / "faq_saeb.json"
    
    pipeline = FaqIngestionPipeline(
        collection_name="faq_inep_collection", 
        batch_size=20
    )
    pipeline.setup_collection()
    
    # Verifica se o arquivo realmente existe antes de tentar rodar a ingestão
    if input_filepath.exists():
        pipeline.process_and_ingest(input_filepath)
    else:
        print(f"Erro: O arquivo de dados não foi encontrado em:\n{input_filepath}")
        print("Por favor, execute o script de extração primeiro.")