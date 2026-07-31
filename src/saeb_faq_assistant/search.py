from qdrant_client import QdrantClient
from qdrant_client.models import (
    Filter, 
    FieldCondition, 
    MatchValue, 
    Prefetch
)
from fastembed import TextEmbedding, SparseTextEmbedding

class FaqSearchEngine:
    def __init__(self, collection_name: str = "faq_inep_collection"):
        self.collection_name = collection_name
        self.client = QdrantClient(url="http://localhost:6333")
        
        print("Carregando modelos de embedding para busca...")
        self.dense_model = TextEmbedding(model_name="sentence-transformers/paraphrase-multilingual-mpnet-base-v2")
        self.sparse_model = SparseTextEmbedding(model_name="Qdrant/bm25")

    def _build_filter(self, survey_name: str):
        """Constrói o filtro de metadados, se um survey for especificado."""
        if not survey_name:
            return None
        return Filter(
            must=[
                FieldCondition(
                    key="survey",
                    match=MatchValue(value=survey_name)
                )
            ]
        )

    def print_results(self, results, search_type: str):
        """Método auxiliar para exibir os resultados de forma legível no terminal."""
        print(f"\n--- Resultados da Busca {search_type.upper()} ---")
        if not results:
            print("Nenhum resultado encontrado.")
            return

        for i, res in enumerate(results, 1):
            # Para search() o payload fica no res.payload. Para query_points(), também.
            payload = res.payload
            score = res.score
            print(f"\n{i}. [Score: {score:.4f}] | Survey: {payload.get('survey')} | Seção: {payload.get('section')}")
            print(f"Pergunta: {payload.get('question')}")
            print(f"Resposta: {payload.get('answer')[:150]}...") # Exibe apenas os primeiros 150 caracteres
        print("-" * 50)

    def semantic_search(self, query: str, survey_filter: str = None, limit: int = 5):
        """Realiza busca vetorial densa (aproximação semântica)."""
        query_vector = list(self.dense_model.embed([query]))[0].tolist()
        q_filter = self._build_filter(survey_filter)

        results = self.client.search(
            collection_name=self.collection_name,
            query_vector=("dense", query_vector),
            query_filter=q_filter,
            limit=limit,
            with_payload=True
        )
        return results

    def lexical_search(self, query: str, survey_filter: str = None, limit: int = 5):
        """Realiza busca vetorial esparsa (correspondência exata de palavras/BM25)."""
        query_sparse_gen = list(self.sparse_model.embed([query]))[0]
        
        # Converte o generator do FastEmbed para o formato esperado pelo Qdrant
        query_vector = {
            "indices": query_sparse_gen.indices.tolist(),
            "values": query_sparse_gen.values.tolist()
        }
        
        q_filter = self._build_filter(survey_filter)

        results = self.client.search(
            collection_name=self.collection_name,
            query_vector=("sparse", query_vector),
            query_filter=q_filter,
            limit=limit,
            with_payload=True
        )
        return results

    def hybrid_search(self, query: str, survey_filter: str = None, limit: int = 5):
        """Realiza busca híbrida utilizando Reciprocal Rank Fusion (RRF)."""
        # Embeddings densos
        query_dense = list(self.dense_model.embed([query]))[0].tolist()
        
        # Embeddings esparsos
        query_sparse_gen = list(self.sparse_model.embed([query]))[0]
        query_sparse = {
            "indices": query_sparse_gen.indices.tolist(),
            "values": query_sparse_gen.values.tolist()
        }
        
        q_filter = self._build_filter(survey_filter)

        # Na API mais recente, query_points é o método ideal para RRF
        results = self.client.query_points(
            collection_name=self.collection_name,
            prefetch=[
                Prefetch(query=query_dense, using="dense", filter=q_filter, limit=limit),
                Prefetch(query=query_sparse, using="sparse", filter=q_filter, limit=limit),
            ],
            query=query, # Passar a string original aciona a fusão (RRF) dos prefetchs
            limit=limit,
            with_payload=True
        )
        
        # O retorno do query_points está na propriedade 'points'
        return results.points


# --- Execução de Teste ---
if __name__ == "__main__":
    search_engine = FaqSearchEngine(collection_name="faq_inep_collection")
    
    user_query = "Como é feita a adesão das escolas?"
    
    # Exemplo 1: Busca Semântica (Sem filtro, procura em ambos os sites)
    sem_results = search_engine.semantic_search(query=user_query, limit=3)
    search_engine.print_results(sem_results, "Semântica")
    
    # Exemplo 2: Busca Lexical (Filtrando apenas para o Saeb)
    lex_results = search_engine.lexical_search(query=user_query, survey_filter="saeb", limit=3)
    search_engine.print_results(lex_results, "Lexical (Apenas Saeb)")
    
    # Exemplo 3: Busca Híbrida (Filtrando apenas para o Censo Escolar)
    hyb_results = search_engine.hybrid_search(query=user_query, survey_filter="censo-escolar", limit=3)
    search_engine.print_results(hyb_results, "Híbrida (Apenas Censo Escolar)")