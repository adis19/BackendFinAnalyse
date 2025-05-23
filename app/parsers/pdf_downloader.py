import os
import requests
from urllib.parse import urlparse
import tempfile

def download_pdf(url: str) -> str:
    """
    Загружает PDF файл по URL
    
    Args:
        url: URL PDF файла
        
    Returns:
        Путь к сохраненному файлу или None в случае ошибки
    """
    try:
        print(f"Загрузка PDF файла с {url}...")
        
        # Настраиваем заголовки для имитации браузера
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9,ru;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Cache-Control': 'max-age=0',
        }
        
        # Сначала получаем домен из URL для установки Referer
        parsed_url = urlparse(url)
        domain = f"{parsed_url.scheme}://{parsed_url.netloc}"
        headers['Referer'] = domain
        
        # Делаем запрос с заголовками
        response = requests.get(url, headers=headers, verify=False, timeout=30)
        response.raise_for_status()
        
        # Проверяем тип контента
        content_type = response.headers.get('Content-Type', '').lower()
        if 'pdf' not in content_type and not url.lower().endswith('.pdf'):
            raise ValueError(f"Получен неверный тип контента: {content_type}")
            
        # Создаем временный файл с расширением .pdf
        temp_dir = tempfile.gettempdir()
        temp_path = os.path.join(temp_dir, f"report_{os.urandom(8).hex()}.pdf")
        
        # Сохраняем содержимое в файл
        with open(temp_path, 'wb') as f:
            f.write(response.content)
            
        print(f"PDF файл успешно загружен и сохранен как {temp_path}")
        return temp_path
        
    except requests.exceptions.RequestException as e:
        print(f"Ошибка при загрузке PDF: {str(e)}")
        return None
    except Exception as e:
        print(f"Неожиданная ошибка при загрузке PDF: {str(e)}")
        return None

def cleanup_pdf(file_path: str) -> None:
    """
    Удаляет временный PDF файл
    
    Args:
        file_path: Путь к файлу для удаления
    """
    try:
        if file_path and os.path.exists(file_path):
            os.remove(file_path)
            print(f"Удален временный файл {file_path}")
    except Exception as e:
        print(f"Ошибка при удалении файла {file_path}: {str(e)}") 