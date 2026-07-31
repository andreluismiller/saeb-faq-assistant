import json
import csv
from pathlib import Path
import sys

current_dir = Path(__file__).resolve().parent
package_dir = current_dir.parent
if str(package_dir) not in sys.path:
    sys.path.insert(0, str(package_dir.parent))

from saeb_faq_assistant.search import FaqSearchEngine

def calculate_metrics(results, expected_id):
    """
    Calcula Hit (0 ou 1) e Reciprocal Rank (RR) para um conjunto de resultados.
    """
    for rank, res in enumerate(results, start=1):
        if res.id == expected_id:
            return 1, 1.0 / rank
    
    # Se o documento esperado não estiver nos resultados
    return 0, 0.0

def evaluate_search_methods():
    # --- Configuração de Caminhos ---
    project_root = current_dir.parent.parent.parent
    data_dir = project_root / "data"
    
    ground_truth_path = data_dir / "ground_truth.json"
    output_csv_path = current_dir / "search_results.csv"
    
    if not ground_truth_path.exists():
        print(f"Erro: Arquivo ground_truth não encontrado em {ground_truth_path}")
        return

    # Carrega os dados de avaliação
    with open(ground_truth_path, "r", encoding="utf-8") as f:
        ground_truth = json.load(f)

    total_queries = len(ground_truth)
    print(f"Iniciando avaliação de {total_queries} queries (paráfrases)...")

    # Inicializa o mecanismo de busca
    search_engine = FaqSearchEngine(collection_name="faq_inep_collection")

    # Estrutura para acumular as métricas
    metrics = {
        "semantic": {"hits": 0, "mrr_sum": 0.0},
        "lexical": {"hits": 0, "mrr_sum": 0.0},
        "hybrid": {"hits": 0, "mrr_sum": 0.0}
    }

    # K = limite de resultados retornados pela busca
    top_k = 5

    # Itera sobre cada pergunta da amostra
    for i, item in enumerate(ground_truth, 1):
        expected_id = item["id"]
        query = item["question"]
        survey_filter = item["survey"]
        
        # 1. Busca Semântica
        res_sem = search_engine.semantic_search(query, survey_filter=survey_filter, limit=top_k)
        hit, rr = calculate_metrics(res_sem, expected_id)
        metrics["semantic"]["hits"] += hit
        metrics["semantic"]["mrr_sum"] += rr
        
        # 2. Busca Lexical
        res_lex = search_engine.lexical_search(query, survey_filter=survey_filter, limit=top_k)
        hit, rr = calculate_metrics(res_lex, expected_id)
        metrics["lexical"]["hits"] += hit
        metrics["lexical"]["mrr_sum"] += rr
        
        # 3. Busca Híbrida
        res_hyb = search_engine.hybrid_search(query, survey_filter=survey_filter, limit=top_k)
        hit, rr = calculate_metrics(res_hyb, expected_id)
        metrics["hybrid"]["hits"] += hit
        metrics["hybrid"]["mrr_sum"] += rr
        
        # Feedback de progresso
        if i % 10 == 0:
            print(f"Processadas {i}/{total_queries} queries...")

    # --- Consolidação e Salvamento dos Resultados ---
    print("\nFinalizando avaliação e gerando relatório...")
    
    # Prepara os dados para o CSV
    csv_data = []
    for method, totals in metrics.items():
        hit_rate = totals["hits"] / total_queries
        mrr = totals["mrr_sum"] / total_queries
        
        csv_data.append({
            "Metodo": method.capitalize(),
            "Hit_Rate": round(hit_rate, 4),
            "MRR": round(mrr, 4)
        })
        
        print(f"[{method.capitalize()}] Hit Rate: {hit_rate:.4f} | MRR: {mrr:.4f}")

    # Salva o CSV na pasta eval
    with open(output_csv_path, mode="w", newline="", encoding="utf-8") as csv_file:
        fieldnames = ["Metodo", "Hit_Rate", "MRR"]
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        
        writer.writeheader()
        for row in csv_data:
            writer.writerow(row)
            
    print(f"\nResultados salvos com sucesso em:\n{output_csv_path}")

if __name__ == "__main__":
    evaluate_search_methods()