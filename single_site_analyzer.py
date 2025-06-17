# single_site_analyzer.py
import requests
import time
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
import ssl
import socket
from collections import defaultdict
import re

class WebsiteDiagnostic:
    def __init__(self, base_url, max_pages=50):
        self.base_url = base_url.rstrip('/')
        self.max_pages = max_pages
        self.visited_urls = set()
        self.broken_links = []
        self.slow_pages = []
        self.seo_issues = []
        self.security_issues = []
        self.performance_data = {}
        
    def check_url_accessibility(self, url, timeout=10):
        """Проверка доступности URL с измерением времени отклика"""
        try:
            start_time = time.time()
            response = requests.get(url, timeout=timeout, allow_redirects=True)
            response_time = time.time() - start_time
            
            return {
                'accessible': True,
                'status_code': response.status_code,
                'response_time': response_time,
                'final_url': response.url,
                'content': response.text if response.status_code == 200 else None
            }
        except requests.exceptions.RequestException as e:
            return {
                'accessible': False,
                'error': str(e),
                'response_time': None
            }
    
    def extract_links(self, html_content, base_url):
        """Извлечение всех ссылок из HTML контента"""
        soup = BeautifulSoup(html_content, 'html.parser')
        links = set()
        
        # Извлекаем ссылки из тегов <a>
        for link in soup.find_all('a', href=True):
            href = link['href']
            full_url = urljoin(base_url, href)
            if self.is_internal_link(full_url):
                links.add(full_url)
        
        return links
    
    def is_internal_link(self, url):
        """Проверка, является ли ссылка внутренней"""
        return urlparse(url).netloc == urlparse(self.base_url).netloc
    
    def analyze_seo(self, html_content, url):
        """Анализ SEO параметров страницы"""
        soup = BeautifulSoup(html_content, 'html.parser')
        issues = []
        
        # Проверка title
        title = soup.find('title')
        if not title or not title.text.strip():
            issues.append(f"Отсутствует title на {url}")
        elif len(title.text) > 60:
            issues.append(f"Title слишком длинный на {url} ({len(title.text)} символов)")
        
        # Проверка meta description
        meta_desc = soup.find('meta', attrs={'name': 'description'})
        if not meta_desc:
            issues.append(f"Отсутствует meta description на {url}")
        elif len(meta_desc.get('content', '')) > 160:
            issues.append(f"Meta description слишком длинное на {url}")
        
        # Проверка H1
        h1_tags = soup.find_all('h1')
        if not h1_tags:
            issues.append(f"Отсутствует H1 на {url}")
        elif len(h1_tags) > 1:
            issues.append(f"Множественные H1 на {url}")
        
        # Проверка alt атрибутов у изображений
        images = soup.find_all('img')
        images_without_alt = [img for img in images if not img.get('alt')]
        if images_without_alt:
            issues.append(f"Изображения без alt атрибутов на {url}: {len(images_without_alt)}")
        
        return issues
    
    def check_security(self, url):
        """Проверка базовых параметров безопасности"""
        issues = []
        
        # Проверка HTTPS
        if not url.startswith('https://'):
            issues.append(f"Отсутствует HTTPS: {url}")
        
        # Проверка SSL сертификата
        try:
            hostname = urlparse(url).hostname
            context = ssl.create_default_context()
            with socket.create_connection((hostname, 443), timeout=10) as sock:
                with context.wrap_socket(sock, server_hostname=hostname) as ssock:
                    cert = ssock.getpeercert()
                    # Здесь можно добавить дополнительные проверки сертификата
        except Exception as e:
            if url.startswith('https://'):
                issues.append(f"Проблемы с SSL сертификатом для {url}: {str(e)}")
        
        return issues
    
    def crawl_website(self):
        """Основной метод сканирования сайта"""
        print(f"Начинаем диагностику сайта: {self.base_url}")
        print(f"Максимальное количество страниц для проверки: {self.max_pages}")
        print("-" * 60)
        
        # Начинаем с главной страницы
        urls_to_visit = [self.base_url]
        
        while urls_to_visit and len(self.visited_urls) < self.max_pages:
            current_url = urls_to_visit.pop(0)
            if current_url in self.visited_urls:
                continue
            
            print(f"Проверяем: {current_url}")
            self.visited_urls.add(current_url)
            
            # Проверяем доступность
            result = self.check_url_accessibility(current_url)
            
            if not result['accessible']:
                self.broken_links.append({
                    'url': current_url,
                    'error': result['error']
                })
                continue
            
            # Записываем данные о производительности
            self.performance_data[current_url] = {
                'response_time': result['response_time'],
                'status_code': result['status_code']
            }
            
            # Проверяем медленные страницы
            if result['response_time'] > 3.0:
                self.slow_pages.append({
                    'url': current_url,
                    'response_time': result['response_time']
                })
            
            # Анализируем SEO
            if result['content']:
                seo_issues = self.analyze_seo(result['content'], current_url)
                self.seo_issues.extend(seo_issues)
                
                # Извлекаем новые ссылки
                new_links = self.extract_links(result['content'], current_url)
                for link in new_links:
                    if link not in self.visited_urls and link not in urls_to_visit:
                        urls_to_visit.append(link)
            
            # Проверяем безопасность
            security_issues = self.check_security(current_url)
            self.security_issues.extend(security_issues)
            
            # Небольшая задержка между запросами
            time.sleep(0.5)
    
    def generate_report(self):
        """Генерация детального отчета"""
        print("\n" + "=" * 60)
        print("           ОТЧЕТ О ДИАГНОСТИКЕ САЙТА")
        print("=" * 60)
        
        # Общая статистика
        print(f"\n📊 ОБЩАЯ СТАТИСТИКА:")
        print(f"Проверено страниц: {len(self.visited_urls)}")
        print(f"Сломанных ссылок: {len(self.broken_links)}")
        print(f"Медленных страниц: {len(self.slow_pages)}")
        print(f"SEO проблем: {len(self.seo_issues)}")
        print(f"Проблем безопасности: {len(self.security_issues)}")
        
        # Производительность
        if self.performance_data:
            avg_response_time = sum(data['response_time'] for data in self.performance_data.values()) / len(self.performance_data)
            print(f"Среднее время отклика: {avg_response_time:.2f} сек")
        
        print("-" * 60)
        
        # Сломанные ссылки
        if self.broken_links:
            print("\n🔴 СЛОМАННЫЕ ССЫЛКИ:")
            for link in self.broken_links[:10]:  # Показываем первые 10
                print(f"  • {link['url']}")
                print(f"    Ошибка: {link['error']}")
        else:
            print("\n✅ Сломанных ссылок не найдено")
        
        # Медленные страницы
        if self.slow_pages:
            print(f"\n🐌 МЕДЛЕННЫЕ СТРАНИЦЫ (время отклика > 3 сек):")
            sorted_slow = sorted(self.slow_pages, key=lambda x: x['response_time'], reverse=True)
            for page in sorted_slow[:10]:
                print(f"  • {page['url']} ({page['response_time']:.2f} сек)")
        else:
            print("\n⚡ Все страницы загружаются быстро")
        
        # SEO проблемы
        if self.seo_issues:
            print(f"\n🔍 SEO ПРОБЛЕМЫ:")
            issue_counts = defaultdict(int)
            for issue in self.seo_issues:
                issue_type = issue.split(' на ')[0] if ' на ' in issue else issue
                issue_counts[issue_type] += 1
            
            for issue_type, count in issue_counts.items():
                print(f"  • {issue_type}: {count} страниц")
            
            print("\nПервые 10 SEO проблем:")
            for issue in self.seo_issues[:10]:
                print(f"  - {issue}")
        else:
            print("\n✅ Критических SEO проблем не найдено")
        
        # Проблемы безопасности
        if self.security_issues:
            print(f"\n🛡️ ПРОБЛЕМЫ БЕЗОПАСНОСТИ:")
            for issue in self.security_issues[:10]:
                print(f"  • {issue}")
        else:
            print("\n🔒 Критических проблем безопасности не найдено")
        
        print("-" * 60)
        # Рекомендации
        print("\n💡 РЕКОМЕНДАЦИИ:")
        
        recommendations = []
        
        if self.broken_links:
            recommendations.append("Исправьте сломанные ссылки для улучшения пользовательского опыта")
        
        if self.slow_pages:
            recommendations.append("Оптимизируйте производительность медленных страниц")
            recommendations.append("Рассмотрите использование CDN и кэширования")
        
        if any("Отсутствует title" in issue for issue in self.seo_issues):
            recommendations.append("Добавьте уникальные title для всех страниц")
        
        if any("meta description" in issue for issue in self.seo_issues):
            recommendations.append("Создайте мета-описания для страниц без них")
        
        if any("alt атрибутов" in issue for issue in self.seo_issues):
            recommendations.append("Добавьте alt-атрибуты для всех изображений")
        
        if any("HTTPS" in issue for issue in self.security_issues):
            recommendations.append("Переведите сайт на HTTPS для безопасности")
        
        if not recommendations:
            recommendations.append("Ваш сайт в хорошем состоянии! Продолжайте мониторинг")
        
        for i, rec in enumerate(recommendations, 1):
            print(f"{i}. {rec}")
        
        print("\n" + "=" * 60)
        print("Диагностика завершена!")
        
        return {
            'total_pages': len(self.visited_urls),
            'broken_links': len(self.broken_links),
            'slow_pages': len(self.slow_pages),
            'seo_issues': len(self.seo_issues),
            'security_issues': len(self.security_issues),
            'avg_response_time': sum(data['response_time'] for data in self.performance_data.values()) / len(self.performance_data) if self.performance_data else 0
        }

# Функция для запуска диагностики
def run_website_diagnostic(url, max_pages=50):
    """Запуск полной диагностики сайта"""
    try:
        diagnostic = WebsiteDiagnostic(url, max_pages)
        diagnostic.crawl_website()
        return diagnostic.generate_report()
    except Exception as e:
        print(f"Ошибка при диагностике: {e}")
        return None

# Пример использования
if __name__ == "__main__":
    # Замените на URL вашего сайта
    website_url = "https://adstable.com"
    
    print("🔍 Утилита диагностики структуры сайта")
    print("=" * 60)
    
    # Можно запросить URL у пользователя
    user_url = input("Введите URL сайта для диагностики (или нажмите Enter для AdsTable.com): ").strip()
    if user_url:
        website_url = user_url
    
    max_pages = input("Максимальное количество страниц для проверки (по умолчанию 50): ").strip()
    max_pages = int(max_pages) if max_pages.isdigit() else 50
    
    # Запускаем диагностику
    results = run_website_diagnostic(website_url, max_pages)
    
    if results:
        print(f"\n📈 Краткая сводка:")
        print(f"Общий балл сайта: {100 - (results['broken_links'] * 10 + results['slow_pages'] * 5 + results['seo_issues'] * 2)}/100")