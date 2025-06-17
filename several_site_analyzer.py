# full_site_analyzer.py
import asyncio
import aiohttp
import json
import sys
import re
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
import argparse
import logging
from urllib.parse import urljoin

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

@dataclass
class MobilePlan:
    """Структура данных мобильного тарифа"""
    name: str
    operator: str
    price: str
    data: str
    calls: str = ""
    sms: str = ""
    validity: str = ""
    additional_info: str = ""
    source_url: str = ""
    
class SiteStructureAnalyzer:
    """Анализатор структуры сайтов норвежских операторов"""
    
    def __init__(self):
        self.session: Optional[aiohttp.ClientSession] = None
        self.plans: List[MobilePlan] = []
        
        # URL для анализа
        self.test_urls = {
            'mobilabonnement.no': 'https://www.mobilabonnement.no',
            'telia': 'https://www.telia.no/privat/mobil/abonnement',
            'telenor': 'https://www.telenor.no/privat/mobil/abonnement',
            'ice': 'https://www.ice.no/mobil/abonnement',
            'mycall': 'https://mycall.no'
        }
        
        # Cookie баннеры - селекторы для поиска и взаимодействия
        self.cookie_selectors = {
            'accept_buttons': [
                '[data-testid*="accept"]', '[data-cy*="accept"]',
                '.cookie-accept', '.accept-cookies', '.gdpr-accept',
                'button[class*="accept"]', 'button[id*="accept"]',
                'button:-soup-contains("Godta")', 'button:-soup-contains("Accept")',
                'button:-soup-contains("Aksepter")', 'button:-soup-contains("OK")',
                '[aria-label*="accept"]', '[title*="accept"]'
            ],
            'close_buttons': [
                '.cookie-close', '.modal-close', '.banner-close',
                'button[aria-label*="close"]', 'button[title*="close"]',
                '.close', '[data-dismiss]', '.dismiss'
            ],
            'banner_containers': [
                '.cookie-banner', '.gdpr-banner', '.consent-banner',
                '.privacy-notice', '#cookie-notice', '#gdpr-notice',
                '[class*="cookie"]', '[class*="consent"]', '[class*="gdpr"]',
                '[id*="cookie"]', '[id*="consent"]', '[role="dialog"]'
            ]
        }
        
        # Заголовки для имитации браузера
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5,no;q=0.3',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none'
        }

    async def __aenter__(self):
        """Асинхронный контекст-менеджер"""
        connector = aiohttp.TCPConnector(limit=10, limit_per_host=5, ttl_dns_cache=300, ssl=False)
        timeout = aiohttp.ClientTimeout(total=30, connect=10)
        self.session = aiohttp.ClientSession(
            headers=self.headers,
            connector=connector,
            timeout=timeout,
            cookie_jar=aiohttp.CookieJar(unsafe=True)
        )
        return self

    async def detect_cookie_banner(self, soup: BeautifulSoup, page_text: str) -> Dict[str, Any]:
        """Детектирование и анализ cookie баннера"""
        cookie_info = {
            'detected': False,
            'banner_elements': [],
            'accept_buttons': [],
            'close_buttons': [],
            'text_indicators': [],
            'banner_text': '',
            'position': 'unknown',
            'modal_overlay': False
        }
        
        # Поиск текстовых индикаторов
        cookie_keywords = {
            'norwegian': ['informasjonskapsler', 'samtykke', 'personvern', 'cookies', 'godta'],
            'english': ['cookies', 'consent', 'privacy', 'accept', 'gdpr', 'tracking'],
            'common': ['cookie', 'gdpr', 'privacy policy', 'data protection']
        }
        
        found_keywords = []
        for lang, keywords in cookie_keywords.items():
            for keyword in keywords:
                if keyword.lower() in page_text:
                    found_keywords.append(f"{keyword} ({lang})")
        
        cookie_info['text_indicators'] = found_keywords
        
        # Поиск контейнеров баннеров
        for selector in self.cookie_selectors['banner_containers']:
            try:
                elements = soup.select(selector)
                if elements:
                    for elem in elements:
                        text = elem.get_text().strip()[:200]
                        if any(kw in text.lower() for kw_list in cookie_keywords.values() for kw in kw_list):
                            cookie_info['banner_elements'].append({
                                'selector': selector,
                                'text': text,
                                'classes': elem.get('class', []),
                                'id': elem.get('id', ''),
                                'position': self._detect_banner_position(elem)
                            })
            except Exception:
                continue
        
        # Поиск кнопок принятия
        for selector in self.cookie_selectors['accept_buttons']:
            try:
                elements = soup.select(selector)
                for elem in elements:
                    text = elem.get_text().strip()
                    if text and any(word in text.lower() for word in ['godta', 'accept', 'ok', 'aksepter']):
                        cookie_info['accept_buttons'].append({
                            'selector': selector,
                            'text': text,
                            'element_type': elem.name,
                            'classes': elem.get('class', []),
                            'id': elem.get('id', '')
                        })
            except Exception:
                continue
        
        # Поиск кнопок закрытия
        for selector in self.cookie_selectors['close_buttons']:
            try:
                elements = soup.select(selector)
                if elements:
                    for elem in elements:
                        cookie_info['close_buttons'].append({
                            'selector': selector,
                            'element_type': elem.name,
                            'classes': elem.get('class', []),
                            'id': elem.get('id', '')
                        })
            except Exception:
                continue
        
        # Проверка на модальное окно
        modal_indicators = soup.select('[role="dialog"], .modal, .overlay, [class*="modal"], [class*="overlay"]')
        cookie_info['modal_overlay'] = len(modal_indicators) > 0
        
        # Определение наличия баннера
        cookie_info['detected'] = (
            len(found_keywords) >= 2 or 
            len(cookie_info['banner_elements']) > 0 or 
            len(cookie_info['accept_buttons']) > 0
        )
        
        # Извлечение основного текста баннера
        if cookie_info['banner_elements']:
            cookie_info['banner_text'] = cookie_info['banner_elements'][0]['text']
            cookie_info['position'] = cookie_info['banner_elements'][0]['position']
        
        return cookie_info
    
    def _detect_banner_position(self, element) -> str:
        """Определение позиции баннера на странице"""
        classes = ' '.join(element.get('class', [])).lower()
        style = element.get('style', '').lower()
        
        position_indicators = {
            'top': ['top', 'header', 'fixed-top'],
            'bottom': ['bottom', 'footer', 'fixed-bottom'],
            'center': ['center', 'modal', 'popup'],
            'overlay': ['overlay', 'fixed', 'absolute']
        }
        
        for position, indicators in position_indicators.items():
            if any(indicator in classes or indicator in style for indicator in indicators):
                return position
        
        return 'unknown'
    
    async def handle_cookie_consent(self, soup: BeautifulSoup, cookie_info: Dict[str, Any]) -> bool:
        """Эмуляция принятия cookie согласия"""
        if not cookie_info['detected']:
            return False
        
        # Логирование найденных элементов для cookie
        logger.info("🍪 Cookie баннер обнаружен:")
        
        if cookie_info['accept_buttons']:
            logger.info(f"   Найдено {len(cookie_info['accept_buttons'])} кнопок принятия:")
            for btn in cookie_info['accept_buttons'][:3]:
                logger.info(f"     • {btn['selector']}: '{btn['text']}'")
        
        if cookie_info['banner_elements']:
            logger.info(f"   Найдено {len(cookie_info['banner_elements'])} баннеров:")
            for banner in cookie_info['banner_elements'][:2]:
                logger.info(f"     • {banner['selector']}: {banner['text'][:50]}...")
        
        # В реальной ситуации здесь бы был код для клика по кнопке
        # Для анализа мы просто возвращаем информацию о том, что можем обработать
        return len(cookie_info['accept_buttons']) > 0

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Закрытие сессии"""
        if self.session:
            await self.session.close()

    def _clean_text(self, text: str) -> str:
        """Очистка текста от лишних символов"""
        if not text:
            return ""
        return re.sub(r'\s+', ' ', text.strip())

    def _extract_price(self, text: str) -> str:
        """Извлечение цены из текста"""
        if not text:
            return ""
        
        # Поиск норвежских крон (NOK, kr)
        price_patterns = [
            r'(\d+(?:,\d+)?)\s*kr',
            r'(\d+(?:,\d+)?)\s*NOK',
            r'kr\s*(\d+(?:,\d+)?)',
            r'NOK\s*(\d+(?:,\d+)?)',
            r'(\d+(?:,\d+)?)\s*,-'
        ]
        
        for pattern in price_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return f"{match.group(1)} kr"
        
        # Если не найдено, возвращаем исходный текст
        return self._clean_text(text)

    def _extract_data_amount(self, text: str) -> str:
        """Извлечение объема данных из текста"""
        if not text:
            return ""
        
        # Паттерны для поиска данных
        data_patterns = [
            r'(\d+(?:,\d+)?)\s*GB',
            r'(\d+(?:,\d+)?)\s*TB',
            r'(\d+(?:,\d+)?)\s*MB',
            r'ubegrenset|unlimited|fri\s*data',
            r'(\d+)\s*giga'
        ]
        
        text_lower = text.lower()
        
        # Проверка на безлимит
        if any(word in text_lower for word in ['ubegrenset', 'unlimited', 'fri data', 'uten grense']):
            return "Unlimited"
        
        for pattern in data_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                if pattern.endswith('giga'):
                    return f"{match.group(1)} GB"
                return match.group(0)
        
        return self._clean_text(text)

    async def analyze_page(self, name: str, url: str) -> Dict[str, Any]:
        """Анализ структуры конкретной страницы"""
        analysis = {
            'name': name,
            'url': url,
            'status': 'error',
            'response_code': None,
            'content_length': 0,
            'title': '',
            'has_cookie_banner': False,
            'cookie_details': {},
            'cookie_handled': False,
            'requires_js': False,
            'common_selectors': {},
            'potential_plan_containers': [],
            'text_content_sample': '',
            'meta_info': {}
        }
        
        try:
            logger.info(f"🔍 Анализ {name}: {url}")
            async with self.session.get(url, allow_redirects=True) as response:
                analysis['response_code'] = response.status
                analysis['final_url'] = str(response.url)
                
                if response.status != 200:
                    analysis['status'] = f'HTTP {response.status}'
                    return analysis
                
                html = await response.text()
                analysis['content_length'] = len(html)
                
                # Парсинг HTML
                soup = BeautifulSoup(html, 'html.parser')
                
                # Основная информация
                title_tag = soup.find('title')
                analysis['title'] = title_tag.get_text().strip() if title_tag else 'Нет заголовка'
                
                # Детектирование и анализ cookie баннера
                cookie_indicators = [
                    'cookie', 'gdpr', 'privacy', 'consent', 'samtykke', 
                    'informasjonskapsler', 'personvern'
                ]
                page_text = html.lower()
                cookie_info = await self.detect_cookie_banner(soup, page_text)
                # Сначала выполняем проверку с помощью более точного анализа
                if cookie_info['detected']:
                    analysis['has_cookie_banner'] = True
                else:
                    # Если не было обнаружено, проверяем текст страницы
                    analysis['has_cookie_banner'] = any(word in page_text for word in cookie_indicators)

                analysis['cookie_details'] = cookie_info
                
                # Попытка обработки cookie согласия
                if cookie_info['detected']:
                    analysis['cookie_handled'] = await self.handle_cookie_consent(soup, cookie_info)
                
                # Проверка на необходимость JavaScript
                js_indicators = [
                    'document.getElementById', 'addEventListener', 'React', 'Vue', 'Angular',
                    'loading...', 'Laster...', 'javascript', 'noscript'
                ]
                analysis['requires_js'] = any(indicator.lower() in page_text for indicator in js_indicators)
                
                # Поиск потенциальных контейнеров планов
                plan_containers = []
                
                # Различные селекторы для карточек планов
                container_selectors = [
                    '.plan', '.product', '.card', '.subscription', '.abonnement',
                    '.offer', '.package', '.tariff', '.mobile-plan',
                    '[class*="plan"]', '[class*="product"]', '[class*="card"]',
                    '[class*="subscription"]', '[id*="plan"]'
                ]
                
                for selector in container_selectors:
                    try:
                        elements = soup.select(selector)
                        if elements:
                            plan_containers.append({
                                'selector': selector,
                                'count': len(elements),
                                'sample_text': elements[0].get_text()[:100] if elements else ''
                            })
                    except:
                        continue
                
                analysis['potential_plan_containers'] = plan_containers
                
                # Анализ общих селекторов
                common_selectors = {
                    'h1': len(soup.select('h1')),
                    'h2': len(soup.select('h2')),
                    'h3': len(soup.select('h3')),
                    '.price': len(soup.select('.price')),
                    '.kr': len(soup.select('.kr')),
                    '[class*="price"]': len(soup.select('[class*="price"]')),
                    '[class*="kr"]': len(soup.select('[class*="kr"]')),
                    '.btn, .button': len(soup.select('.btn, .button')),
                    'form': len(soup.select('form')),
                    'table': len(soup.select('table'))
                }
                analysis['common_selectors'] = {k: v for k, v in common_selectors.items() if v > 0}
                
                # Метаинформация
                meta_tags = {}
                for meta in soup.find_all('meta'):
                    name = meta.get('name') or meta.get('property', '')
                    content = meta.get('content', '')
                    if name and content:
                        meta_tags[name] = content[:100]
                analysis['meta_info'] = meta_tags
                
                # Образец текстового контента
                body = soup.find('body')
                if body:
                    text_content = body.get_text()
                    # Очистка и первые 500 символов
                    clean_text = ' '.join(text_content.split())
                    analysis['text_content_sample'] = clean_text[:500] + '...' if len(clean_text) > 500 else clean_text
                
                analysis['status'] = 'success'
                logger.info(f"✅ {name}: Анализ завершен ({analysis['content_length']} символов)")
                
        except asyncio.TimeoutError:
            analysis['status'] = 'timeout'
            logger.warning(f"⏱️ {name}: Таймаут")
        except Exception as e:
            analysis['status'] = f'error: {str(e)}'
            logger.error(f"❌ {name}: {e}")
            
        return analysis

    async def analyze_all_sites(self) -> Dict[str, Any]:
        """Анализ всех сайтов"""
        logger.info("🚀 Начинаем анализ структуры сайтов")
        
        tasks = []
        for name, url in self.test_urls.items():
            task = self.analyze_page(name, url)
            tasks.append(task)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        analysis_results = {}
        for i, result in enumerate(results):
            name = list(self.test_urls.keys())[i]
            if isinstance(result, Exception):
                analysis_results[name] = {
                    'name': name,
                    'status': f'exception: {str(result)}',
                    'url': self.test_urls[name]
                }
            else:
                analysis_results[name] = result
        
        return analysis_results

    def print_analysis_report(self, results: Dict[str, Any]):
        """Вывод отчета анализа"""
        print("\n" + "="*80)
        print("📊 ОТЧЕТ АНАЛИЗА СТРУКТУРЫ САЙТОВ")
        print("="*80)
        
        for name, analysis in results.items():
            print(f"\n🌐 {analysis['name'].upper()}")
            print(f"   URL: {analysis['url']}")
            print(f"   Статус: {analysis['status']}")
            
            if analysis['status'] == 'success':
                print(f"   HTTP код: {analysis['response_code']}")
                print(f"   Размер: {analysis['content_length']:,} символов")
                print(f"   Заголовок: {analysis['title']}")
                print(f"   Cookie баннер: {'Да' if analysis['has_cookie_banner'] else 'Нет'}")
                
                # Детальная информация о cookie
                if analysis['has_cookie_banner'] and analysis.get('cookie_details'):
                    cookie_details = analysis['cookie_details']
                    print(f"   🍪 Cookie детали:")
                    print(f"      • Обработан: {'Да' if analysis.get('cookie_handled') else 'Нет'}")
                    print(f"      • Позиция: {cookie_details.get('position', 'неизвестно')}")
                    print(f"      • Модальное окно: {'Да' if cookie_details.get('modal_overlay') else 'Нет'}")
                    
                    if cookie_details.get('accept_buttons'):
                        print(f"      • Кнопки принятия: {len(cookie_details['accept_buttons'])}")
                        for btn in cookie_details['accept_buttons'][:2]:
                            print(f"        - '{btn['text']}' ({btn['selector']})")
                    
                    if cookie_details.get('text_indicators'):
                        indicators = ', '.join(cookie_details['text_indicators'][:3])
                        print(f"      • Ключевые слова: {indicators}")
                
                print(f"   Требует JS: {'Да' if analysis['requires_js'] else 'Нет'}")
                
                if analysis['potential_plan_containers']:
                    print(f"   📦 Потенциальные контейнеры планов:")
                    for container in analysis['potential_plan_containers'][:5]:
                        print(f"      • {container['selector']}: {container['count']} элементов")
                        if container['sample_text'].strip():
                            sample = container['sample_text'].strip()[:60]
                            print(f"        Пример: {sample}{'...' if len(sample) == 60 else ''}")
                else:
                    print(f"   📦 Контейнеры планов: Не найдены")
                
                if analysis['common_selectors']:
                    print(f"   🎯 Полезные селекторы:")
                    for selector, count in list(analysis['common_selectors'].items())[:5]:
                        print(f"      • {selector}: {count}")
                
                # Образец контента
                if analysis['text_content_sample']:
                    print(f"   📝 Образец контента:")
                    sample_lines = analysis['text_content_sample'][:200].split('\n')[:3]
                    for line in sample_lines:
                        if line.strip():
                            print(f"      {line.strip()[:70]}...")
            
            print("-" * 60)
        
        # Рекомендации
        self.print_recommendations(results)

    def print_recommendations(self, results: Dict[str, Any]):
        """Рекомендации по оптимизации парсинга"""
        print("\n" + "🎯 РЕКОМЕНДАЦИИ ПО ПАРСИНГУ")
        print("="*60)
        
        successful_sites = [r for r in results.values() if r['status'] == 'success']
        
        if not successful_sites:
            print("❌ Нет успешно проанализированных сайтов для рекомендаций")
            return
        
        # Анализ общих паттернов
        print("\n📋 Стратегии парсинга:")
        
        # Cookie баннеры - детальный анализ
        cookie_sites = [s for s in successful_sites if s.get('has_cookie_banner')]
        if cookie_sites:
            print(f"\n🍪 Cookie баннеры найдены на {len(cookie_sites)} сайтах:")
            for site in cookie_sites:
                cookie_details = site.get('cookie_details', {})
                handled = "✅" if site.get('cookie_handled') else "❌"
                position = cookie_details.get('position', 'неизвестно')
                modal = "модальное" if cookie_details.get('modal_overlay') else "баннер"
                
                print(f"   • {site['name']} {handled} - {position} ({modal})")
                
                # Показать лучшие селекторы для автоматизации
                accept_buttons = cookie_details.get('accept_buttons', [])
                if accept_buttons:
                    best_button = accept_buttons[0]  # Первый обычно лучший
                    print(f"     Рекомендуемый селектор: {best_button['selector']}")
                    print(f"     Текст кнопки: '{best_button['text']}'")
            
            print("   📋 Стратегии обработки:")
            print("     1. Selenium/Playwright для автоматического клика")
            print("     2. Предустановленные cookie для обхода")
            print("     3. Эмуляция согласия через HTTP заголовки")
        else:
            print("\n🍪 Cookie баннеры не обнаружены")
        
        # JavaScript зависимости
        js_sites = [s for s in successful_sites if s.get('requires_js')]
        if js_sites:
            print(f"\n⚡ JavaScript требуется на {len(js_sites)} сайтах:")
            for site in js_sites:
                print(f"   • {site['name']}")
            print("   Рекомендация: Использовать Selenium или Playwright для рендеринга")
        
        # Общие селекторы
        all_selectors = {}
        for site in successful_sites:
            for selector, count in site.get('common_selectors', {}).items():
                if selector not in all_selectors:
                    all_selectors[selector] = []
                all_selectors[selector].append((site['name'], count))
        
        print(f"\n🎯 Универсальные селекторы:")
        for selector, site_counts in sorted(all_selectors.items(), 
                                          key=lambda x: len(x[1]), reverse=True):
            if len(site_counts) >= 2:  # Селектор есть минимум на 2 сайтах
                sites_str = ', '.join([f"{name}({count})" for name, count in site_counts[:3]])
                print(f"   • {selector}: {sites_str}")
        
        # Контейнеры планов
        print(f"\n📦 Анализ контейнеров планов:")
        for site in successful_sites:
            containers = site.get('potential_plan_containers', [])
            if containers:
                print(f"\n   🌐 {site['name'].upper()}:")
                for container in containers[:3]:
                    print(f"      ✓ {container['selector']} ({container['count']} элементов)")
            else:
                print(f"   ❌ {site['name']}: Контейнеры не найдены")
        
        # Специальные рекомендации
        print(f"\n💡 Специальные рекомендации:")
        
        # Проверка размеров страниц
        large_pages = [s for s in successful_sites if s.get('content_length', 0) > 500000]
        if large_pages:
            print(f"   📄 Большие страницы (>500KB):")
            for site in large_pages:
                size_kb = site['content_length'] // 1024
                print(f"      • {site['name']}: {size_kb}KB - возможна медленная загрузка")
        
        # Анализ заголовков для понимания структуры
        title_patterns = {}
        for site in successful_sites:
            title = site.get('title', '').lower()
            words = [w for w in title.split() if len(w) > 3]
            for word in words[:3]:  # Первые 3 значимых слова
                if word not in title_patterns:
                    title_patterns[word] = []
                title_patterns[word].append(site['name'])
        
        common_title_words = {k: v for k, v in title_patterns.items() if len(v) >= 2}
        if common_title_words:
            print(f"   🔤 Общие ключевые слова в заголовках:")
            for word, sites in sorted(common_title_words.items(), 
                                    key=lambda x: len(x[1]), reverse=True):
                sites_str = ', '.join(sites)
                print(f"      • '{word}': {sites_str}")

    def generate_cookie_automation_code(self, results: Dict[str, Any]) -> str:
        """Генерация кода для автоматической обработки cookie"""
        successful_sites = [r for r in results.values() if r['status'] == 'success']
        cookie_sites = [s for s in successful_sites if s.get('has_cookie_banner')]
        
        if not cookie_sites:
            return "# Cookie баннеры не найдены"
        
        code_lines = [
            "# Автоматическая обработка cookie согласий",
            "from selenium import webdriver",
            "from selenium.webdriver.common.by import By",
            "from selenium.webdriver.support.ui import WebDriverWait",
            "from selenium.webdriver.support import expected_conditions as EC",
            "import time",
            "",
            "def handle_cookie_consent(driver, site_name):",
            "    \"\"\"Обработка cookie согласия для конкретного сайта\"\"\"",
            "    cookie_selectors = {"
        ]
        
        # Генерация селекторов для каждого сайта
        for site in cookie_sites:
            cookie_details = site.get('cookie_details', {})
            accept_buttons = cookie_details.get('accept_buttons', [])
            
            if accept_buttons:
                site_name = site['name'].replace('.', '_').replace('-', '_')
                selectors = [btn['selector'] for btn in accept_buttons[:3]]
                code_lines.append(f"        '{site_name}': {selectors},")
        
        code_lines.extend([
            "    }",
            "",
            "    if site_name not in cookie_selectors:",
            "        return False",
            "",
            "    for selector in cookie_selectors[site_name]:",
            "        try:",
            "            # Ожидание появления элемента",
            "            element = WebDriverWait(driver, 5).until(",
            "                EC.element_to_be_clickable((By.CSS_SELECTOR, selector))",
            "            )",
            "            element.click()",
            "            print(f'✅ Cookie согласие принято: {selector}')",
            "            time.sleep(1)  # Небольшая пауза",
            "            return True",
            "        except Exception as e:",
            "            continue",
            "",
            "    print(f'❌ Не удалось обработать cookie для {site_name}')",
            "    return False",
            "",
            "# Пример использования:",
            "# driver = webdriver.Chrome()",
            "# driver.get('https://example.com')",
            "# handle_cookie_consent(driver, 'example_site')"
        ])
        
        return '\n'.join(code_lines)
        """Экспорт результатов в JSON"""
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(results, f, ensure_ascii=False, indent=2)
            print(f"\n💾 Результаты сохранены в {filename}")
        except Exception as e:
            logger.error(f"Ошибка сохранения: {e}")

    def export_results(self, results: Dict[str, Any], filename: str = 'site_analysis.json'):
        """Экспорт результатов в JSON"""
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(results, f, ensure_ascii=False, indent=2)
            print(f"\n💾 Результаты сохранены в {filename}")
        except Exception as e:
            logger.error(f"Ошибка сохранения: {e}")
    
    def add_custom_url(self, name: str, url: str):
        """Добавление пользовательского URL для анализа"""
        self.test_urls[name] = url
        logger.info(f"Добавлен URL: {name} -> {url}")

async def main():
    """Основная функция"""
    parser = argparse.ArgumentParser(description='Анализатор структуры сайтов')
    parser.add_argument('--export', '-e', help='Экспорт в JSON файл')
    parser.add_argument('--export-cookies', help='Экспорт кода автоматизации cookie')
    parser.add_argument('--url', nargs=2, metavar=('NAME', 'URL'), 
                       help='Добавить пользовательский URL: --url mysite https://example.com')
    parser.add_argument('--silent', '-s', action='store_true', 
                       help='Минимальный вывод')
    args = parser.parse_args()
    
    if args.silent:
        logging.getLogger().setLevel(logging.WARNING)
    
    async with SiteStructureAnalyzer() as analyzer:
        # Добавление пользовательского URL
        if args.url:
            analyzer.add_custom_url(args.url[0], args.url[1])
        
        # Анализ сайтов
        results = await analyzer.analyze_all_sites()
        
        # Вывод отчета
        if not args.silent:
            analyzer.print_analysis_report(results)
        
        # Экспорт результатов
        if args.export:
            analyzer.export_results(results, args.export)
        
        # Экспорт кода автоматизации cookie
        if args.export_cookies:
            analyzer.export_cookie_automation(results, args.export_cookies)
        
        # Краткая статистика
        successful = len([r for r in results.values() if r['status'] == 'success'])
        total = len(results)
        print(f"\n🎉 Анализ завершен: {successful}/{total} сайтов успешно обработано")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n⏹️ Анализ прерван пользователем")
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}")
        sys.exit(1)