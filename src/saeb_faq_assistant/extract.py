import requests
from bs4 import BeautifulSoup
import json
from pathlib import Path

from saeb_faq_assistant.paths import DATASET_PATH

def scrape_inep_faqs():
    """
    Função para raspar perguntas frequentes do INEP.
    """
    sources = [
        {
            "url": "https://www.gov.br/inep/pt-br/acesso-a-informacao/perguntas-frequentes/sistema-de-avaliacao-da-educacao-basica-saeb",
            "survey": "saeb"
        },
        {
            "url": "https://www.gov.br/inep/pt-br/acesso-a-informacao/perguntas-frequentes/censo-escolar",
            "survey": "censo-escolar"
        }
    ]
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
    }
    
    faq_list = []
    current_id = 1
    
    for source in sources:
        print(f"Iniciando extração de: {source['survey']}...")
        response = requests.get(source['url'], headers=headers)
        
        if response.status_code != 200:
            print(f"Erro ao acessar a página {source['url']}: Status {response.status_code}")
            continue
            
        soup = BeautifulSoup(response.content, "html.parser")
        
        content_core = soup.find('div', id='content-core')
        if not content_core:
            print(f"Não foi possível encontrar a div#content-core na página {source['survey']}.")
            continue

        main_ul = content_core.find('ul')
        if not main_ul:
            print(f"Não foi possível encontrar a lista de seções na página {source['survey']}.")
            continue
            
        for section_li in main_ul.find_all('li', recursive=False):
            section_a = section_li.find('a', class_='toggle')
            if not section_a:
                continue
                
            section_name = section_a.get_text(strip=True)
            
            questions_ul = section_li.find('ul')
            if not questions_ul:
                continue
                
            for q_li in questions_ul.find_all('li', recursive=False):
                question_a = q_li.find('a', class_='toggle')
                answer_div = q_li.find('div', class_='conteudo')
                
                if question_a and answer_div:
                    if answer_div.find('table') is not None:
                        continue
                        
                    question_text = question_a.get_text(strip=True)
                    answer_text = answer_div.get_text(separator='\n', strip=True)
                    
                    faq_list.append({
                        "id": current_id,
                        "survey": source['survey'],
                        "section": section_name,
                        "question": question_text,
                        "answer": answer_text
                    })
                    
                    current_id += 1
                    
    
    with open(DATASET_PATH, "w", encoding="utf-8") as f:
        json.dump(faq_list, f, ensure_ascii=False, indent=4)
        
    print(f"Scraping concluído! Foram extraídos {len(faq_list)} itens e salvos em:\n{DATASET_PATH}")

if __name__ == "__main__":
    scrape_inep_faqs()