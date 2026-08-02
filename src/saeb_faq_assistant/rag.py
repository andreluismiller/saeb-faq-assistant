import os
import time
from qdrant_client import QdrantClient
from qdrant_client.models import Prefetch, SparseVector, FusionQuery, Fusion
from fastembed import TextEmbedding, SparseTextEmbedding
from openai import OpenAI

class RAGSystem:
    def __init__(self, collection_name="faq_inep_collection"):
        """Inicializa o sistema RAG integrando Qdrant, FastEmbed e LLM via Groq."""
        self.collection_name = collection_name
        
        # Cliente LLM Groq API usando a compatibilidade com OpenAI
        self.llm_client = OpenAI(
            api_key=os.environ.get("GROQ_API_KEY"),
            base_url="https://api.groq.com/openai/v1"
        )
        self.model_name = "llama-3.3-70b-versatile"
        
        # Conexão com o banco vetorial local
        self.qdrant_client = QdrantClient(url="http://localhost:6333")
        
        # Inicialização dos modelos de embedding (mesmos usados na ingestão)
        print("Carregando modelos de embedding...")
        self.dense_model = TextEmbedding(model_name="sentence-transformers/paraphrase-multilingual-mpnet-base-v2")
        self.sparse_model = SparseTextEmbedding(model_name="Qdrant/bm25")
        
        # Tabela de preços do Groq (valores aproximados em USD por 1M de tokens)
        self.pricing = {
            'llama-3.3-70b-versatile': {
                'prompt': 0.59,      # $0.59 por 1M de tokens de entrada
                'completion': 0.79   # $0.79 por 1M de tokens de saída
            }
        }
        
    def check_collection_exists(self):
        """Verifica se a coleção existe no Qdrant."""
        try:
            return self.qdrant_client.collection_exists(self.collection_name)
        except Exception as e:
            print(f"Erro ao verificar a coleção: {e}")
            return False

    def hybrid_search(self, query: str, limit: int = 5):
        """
        Executa busca híbrida (Semântica + Lexical) com Reciprocal Rank Fusion (RRF).
        """
        query_dense = list(self.dense_model.embed([query]))[0].tolist()
        
        query_sparse_gen = list(self.sparse_model.embed([query]))[0]
                
        query_sparse = SparseVector(
            indices=query_sparse_gen.indices.tolist(),
            values=query_sparse_gen.values.tolist()
        )
        
        results = self.qdrant_client.query_points(
            collection_name=self.collection_name,
            prefetch=[
                Prefetch(query=query_dense, using="dense", limit=limit),
                Prefetch(query=query_sparse, using="sparse", limit=limit),
            ],
            query=FusionQuery(fusion=Fusion.RRF),
            limit=limit,
            with_payload=True
        )
        
        return results.points


    def build_prompt(self, user_query: str, search_results: list):
        """Constrói o prompt instruindo o modelo a responder com base no contexto em Português."""
        prompt_template = """
Você é um assistente especialista do INEP (Instituto Nacional de Estudos e Pesquisas Educacionais Anísio Teixeira).
Utilize APENAS as informações presentes no "Contexto" abaixo para responder à pergunta do usuário.

REGRAS:
- Responda em Português do Brasil.
- Baseie-se unicamente nas perguntas e respostas fornecidas. Se a informação não estiver no contexto, diga que não possui a informação.
- Retorne apenas a resposta direta e formatada em Markdown (sem comentários adicionais ou JSON).

Contexto:
{context}

Pergunta do Usuário:
{question}

Resposta:
""".strip()

        context = ""
        # Monta o contexto juntando a pergunta original da FAQ e a resposta oficial
        for point in search_results:
            payload = point.payload
            context += f"Documento da seção: {payload.get('section')} (Origem: {payload.get('survey')})\n"
            context += f"Pergunta FAQ: {payload.get('question')}\n"
            context += f"Resposta FAQ: {payload.get('answer')}\n\n"
            
        return prompt_template.format(question=user_query, context=context).strip()

    def generate_response(self, prompt: str):
        """Envia o prompt ao LLM e retorna a resposta e o uso de tokens."""
        response = self.llm_client.chat.completions.create(
            model=self.model_name,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1 # Temperatura baixa para respostas mais factuais e precisas
        )
        
        usage = response.usage
        return (
            response.choices[0].message.content,
            usage.prompt_tokens,
            usage.completion_tokens,
            usage.total_tokens
        )

    def calculate_cost(self, prompt_tokens: int, completion_tokens: int):
        """Calcula o custo financeiro da chamada à API em Dólares (USD)."""
        if self.model_name not in self.pricing:
            return 0.0
            
        prompt_cost = (prompt_tokens / 1_000_000) * self.pricing[self.model_name]['prompt']
        completion_cost = (completion_tokens / 1_000_000) * self.pricing[self.model_name]['completion']
        
        return prompt_cost + completion_cost

    def execute_rag_pipeline(self, user_query: str):
        """
        Orquestra o workflow completo: Validação -> Busca -> Prompt -> LLM -> Métricas.
        """
        start_time = time.time()
        
        # 1. Validação de infraestrutura
        if not self.check_collection_exists():
            raise Exception(f"A coleção '{self.collection_name}' não foi encontrada no Qdrant.")
            
        # 2. Recuperação de contexto (Busca Híbrida)
        search_results = self.hybrid_search(user_query)
        
        # 3. Construção do Prompt
        prompt = self.build_prompt(user_query, search_results)
        
        # 4. Inferência no LLM
        answer, prompt_tokens, completion_tokens, total_tokens = self.generate_response(prompt)
        
        # 5. Fechamento de métricas
        response_time = time.time() - start_time
        monetary_cost = self.calculate_cost(prompt_tokens, completion_tokens)
        
        # Extração dos metadados dos resultados para facilitar visualização (opcional)
        context_used = [{"score": p.score, "survey": p.payload.get('survey')} for p in search_results]
        
        return {
            'answer': answer,
            'model_used': self.model_name,
            'response_time_seconds': round(response_time, 4),
            'prompt_tokens': prompt_tokens,
            'completion_tokens': completion_tokens,
            'total_tokens': total_tokens,
            'cost_usd': monetary_cost,
            'context_sources': context_used
        }

if __name__ == "__main__":
    # Certifique-se de exportar a variável antes de rodar: 
    # export GROQ_API_KEY="sua-chave-aqui"
    
    rag_system = RAGSystem()
    pergunta = "Como faço para aderir ao Saeb?"
    
    resultado = rag_system.execute_rag_pipeline(pergunta)
    
    print("\n=== RESPOSTA GERADA ===")
    print(resultado['answer'])
    print("\n=== TELEMETRIA ===")
    print(f"Modelo: {resultado['model_used']}")
    print(f"Tempo de Resposta: {resultado['response_time_seconds']}s")
    print(f"Tokens (Prompt): {resultado['prompt_tokens']}")
    print(f"Tokens (Conclusão): {resultado['completion_tokens']}")
    print(f"Tokens (Total): {resultado['total_tokens']}")
    print(f"Custo Estimado: ${resultado['cost_usd']:.6f}")