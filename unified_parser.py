# unified_parser.py
import asyncio
import aiohttp
import json
import sys
import re
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
import argparse
import logging
from concurrent.futures import ThreadPoolExecutor

// Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

@dataclass
class MobilePlan:
    """Структура мобильного тарифа"""
    name: str
    operator: str
    price: str
    data: str
    calls: str = ""
    sms: str = ""
    validity: str = ""
    additional_info: str = ""
    source_url: str = ""

@dataclass
class SiteAnalysis:
    """Результат анализа сайта"""
    name: str
    url: str
    status: str
    has_cookie_banner: bool
    cookie_selectors: List[str]
    requires_js: bool
    plan_containers: List[Dict[str, Any]]
    optimal_selectors: Dict[str, str]

class UnifiedNorwayMobileParser:
    """Объединенный парсер норвежских мобильных тарифов с анализом структуры"""
    
    def __init__(self):
        self.session: Optional[aiohttp.ClientSession] = None
        self.plans: List[MobilePlan] = []
        self.site_analysis: Dict[str, SiteAnalysis] = {}
        
        // Базовая конфигурация операторов
        self.operators_config = {
            'telia': {
                'url': 'https://www.telia.no/privat/mobil/abonnement',
                'name': 'Telia',
                'fallback_selectors': {
                    'plan_cards': '.product-card, .plan-card, [data-testid*="plan"]',
                    'plan_name': 'h3, .plan-name, .product-title',
                    'price': '.price, .monthly-price, [data-testid*="price"]',
                    'data': '.data-amount, .gb-amount, [data-testid*="data"]'
                }
            },
            'telenor': {
                'url': 'https://www.telenor.no/privat/mobil/abonnement',
                'name': 'Telenor', 
                'fallback_selectors': {
                    'plan_cards': '.product-card, .plan-item, [data-cy*="plan"]',
                    'plan_name': 'h3, .plan-title, .product-name',
                    'price': '.price, .amount, [data-cy*="price"]',
                    'data': '.data-text, .gb-text, [data-cy*="data"]'
                }
            },
            'ice': {
                'url': 'https://www.ice.no/mobil/abonnement',
                'name': 'Ice',
                'fallback_selectors': {
                    'plan_cards': '.plan-card, .product-item',
                    'plan_name': 'h3, .plan-name, .title',
                    'price': '.price, .cost, .monthly-fee',
                    'data': '.data-limit, .gb-limit'
                }
            },
            'mycall': {
                'url': 'https://mycall.no',
                'name': 'MyCall',
                'fallback_selectors': {
                    'plan_cards': '.plan-box, .offer-card',
                    'plan_name': 'h3, .plan-title',
                    'price': '.price, .monthly-price',
                    'data': '.data-amount, .gb-info'
                }
            }
        }
        
        // Cookie-баннер селекторы для автоматизации
        self.cookie_selectors = {
            'accept_patterns': [
                '[data-testid*="accept"]', '[data-cy*="accept"]',
                '.cookie-accept', '.accept-cookies', '.gdpr-accept',
                'button[class*="accept"]', 'button[id*="accept"]',
                'button:-soup-contains("Godta")', 'button:-soup-contains("Accept")',
                'button:-soup-contains("Aksepter")', '[aria-label*="accept"]'
            ],
            'banner_patterns': [
                '.cookie-banner', '.gdpr-banner', '.consent-banner',
                '#cookie-notice', '[class*="cookie"]', '[role="dialog"]'
            ]
        }
        
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5,no;q=0.3',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive'
        }

    async def __aenter__(self):
        connector = aiohttp.TCPConnector(
            limit=10, limit_per_host=3, ttl_dns_cache=300, ssl=False
        )
        timeout = aiohttp.ClientTimeout(total=30, connect=10)
        self.session = aiohttp.ClientSession(
            headers=self.headers,
            connector=connector,
            timeout=timeout,
            cookie_jar=aiohttp.CookieJar(unsafe=True)
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    def _clean_text(self, text: str) -> str:
        """Очистка текста"""
        return re.sub(r'\s+', ' ', text.strip()) if text else ""

    def _extract_price(self, text: str) -> str:
        """Извлечение цены из текста"""
        if not text:
            return ""
        
        price_patterns = [
            r'(\d+(?:[,\.]\d+)?)\s*kr\b',
            r'(\d+(?:[,\.]\d+)?)\s*NOK\b', 
            r'\bkr\s*(\d+(?:[,\.]\d+)?)',
            r'(\d+(?:[,\.]\d+)?)\s*,-'
        ]
        
        for pattern in price_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                price = match.group(1).replace(',', '.')
                return f"{price} kr"
        
        return self._clean_text(text)

    def _extract_data_amount(self, text: str) -> str:
        """Извлечение объема данных"""
        if not text:
            return ""
        
        text_lower = text.lower()
        
        // Проверка на безлимит
        unlimited_keywords = ['ubegrenset', 'unlimited', 'fri data', 'uten grense']
        if any(keyword in text_lower for keyword in unlimited_keywords):
            return "Unlimited"
        
        data_patterns = [
            r'(\d+(?:[,\.]\d+)?)\s*GB\b',
            r'(\d+(?:[,\.]\d+)?)\s*TB\b',
            r'(\d+(?:[,\.]\d+)?)\s*MB\b',
            r'(\d+)\s*giga\b'
        ]
        
        for pattern in data_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                amount = match.group(1).replace(',', '.')
                unit = 'GB' if 'giga' in pattern else match.group(0)[-2:]
                return f"{amount} {unit}"
        
        return self._clean_text(text)

    async def _fetch_with_retry(self, url: str, max_retries: int = 3) -> Optional[str]:
        """Загрузка страницы с повторными попытками"""
        for attempt in range(max_retries):
            try:
                logger.info(f"Загрузка {url} (попытка {attempt + 1})")
                async with self.session.get(url, allow_redirects=True) as response:
                    if response.status == 200:
                        content = await response.text()
                        logger.info(f"✅ Успешно загружено ({len(content)} символов)")
                        return content
                    else:
                        logger.warning(f"HTTP {response.status}")
            except asyncio.TimeoutError:
                logger.warning(f"⏱️ Таймаут")
            except Exception as e:
                logger.error(f"Ошибка: {e}")
            
            if attempt < max_retries - 1:
                await asyncio.sleep(2 ** attempt)
        
        return None

    def _detect_cookie_elements(self, soup: BeautifulSoup) -> Dict[str, List[str]]:
        """Детектирование cookie элементов"""
        cookie_elements = {
            'accept_buttons': [],
            'banners': []
        }
        
        // Поиск кнопок принятия
        for pattern in self.cookie_selectors['accept_patterns']:
            try:
                elements = soup.select(pattern)
                for elem in elements:
                    text = elem.get_text().strip().lower()
                    if any(word in text for word in ['godta', 'accept', 'ok', 'aksepter']):
                        cookie_elements['accept_buttons'].append(pattern)
                        break
            except:
                continue
        
        // Поиск баннеров
        for pattern in self.cookie_selectors['banner_patterns']:
            try:
                if soup.select(pattern):
                    cookie_elements['banners'].append(pattern)
            except:
                continue
        
        return cookie_elements

    def _analyze_plan_containers(self, soup: BeautifulSoup) -> List[Dict[str, Any]]:
        """Анализ контейнеров с планами"""
        containers = []
        
        container_patterns = [
            '.plan', '.product', '.card', '.subscription', '.abonnement',
            '.offer', '.package', '.tariff', '[class*="plan"]',
            '[class*="product"]', '[class*="subscription"]'
        ]
        
        for pattern in container_patterns:
            try:
                elements = soup.select(pattern)
                if len(elements) >= 2:  // Минимум 2 элемента для валидности
                    sample_text = elements[0].get_text()[:100] if elements else ""
                    containers.append({
                        'selector': pattern,
                        'count': len(elements),
                        'sample_text': sample_text,
                        'confidence': self._calculate_container_confidence(elements)
                    })
            except:
                continue
        
        // Сортировка по уверенности
        return sorted(containers, key=lambda x: x['confidence'], reverse=True)

    def _calculate_container_confidence(self, elements: List) -> float:
        """Расчет уверенности в контейнере планов"""
        if not elements:
            return 0.0
        
        confidence = 0.0
        keywords = ['kr', 'gb', 'plan', 'mobil', 'abonnement', 'måned']
        
        for elem in elements[:3]:  // Проверяем первые 3 элемента
            text = elem.get_text().lower()
            keyword_matches = sum(1 for keyword in keywords if keyword in text)
            confidence += keyword_matches / len(keywords)
        
        return confidence / min(len(elements), 3)

    def _optimize_selectors(self, containers: List[Dict[str, Any]], 
                          fallback_selectors: Dict[str, str]) -> Dict[str, str]:
        """Оптимизация селекторов на основе анализа"""
        optimized = fallback_selectors.copy()
        
        if containers:
            best_container = containers[0]
            if best_container['confidence'] > 0.5:
                optimized['plan_cards'] = best_container['selector']
        
        return optimized

    async def analyze_site_structure(self, operator_key: str) -> SiteAnalysis:
        """Анализ структуры сайта оператора"""
        config = self.operators_config[operator_key]
        
        logger.info(f"🔍 Анализ структуры {config['name']}")
        
        html = await self._fetch_with_retry(config['url'])
        if not html:
            return SiteAnalysis(
                name=config['name'], url=config['url'], status='failed',
                has_cookie_banner=False, cookie_selectors=[],
                requires_js=False, plan_containers=[],
                optimal_selectors=config['fallback_selectors']
            )
        
        soup = BeautifulSoup(html, 'html.parser')
        
        // Анализ cookie элементов
        cookie_elements = self._detect_cookie_elements(soup)
        has_cookie_banner = bool(cookie_elements['accept_buttons'] or cookie_elements['banners'])
        
        // Проверка на JavaScript
        requires_js = any(indicator in html.lower() for indicator in [
            'document.getelementbyid', 'react', 'vue', 'angular', 'loading...'
        ])
        
        // Анализ контейнеров планов
        plan_containers = self._analyze_plan_containers(soup)
        
        // Оптимизация селекторов
        optimal_selectors = self._optimize_selectors(plan_containers, config['fallback_selectors'])
        
        analysis = SiteAnalysis(
            name=config['name'],
            url=config['url'],
            status='success',
            has_cookie_banner=has_cookie_banner,
            cookie_selectors=cookie_elements['accept_buttons'],
            requires_js=requires_js,
            plan_containers=plan_containers,
            optimal_selectors=optimal_selectors
        )
        
        logger.info(f"✅ Анализ {config['name']} завершен")
        return analysis

    def _parse_plans_from_html(self, html: str, analysis: SiteAnalysis) -> List[MobilePlan]:
        """Парсинг планов на основе анализа структуры"""
        plans = []
        
        try:
            soup = BeautifulSoup(html, 'html.parser')
            selectors = analysis.optimal_selectors
            
            // Поиск карточек планов
            plan_elements = []
            for selector in selectors['plan_cards'].split(', '):
                elements = soup.select(selector.strip())
                plan_elements.extend(elements)
            
            logger.info(f"Найдено {len(plan_elements)} карточек для {analysis.name}")
            
            for element in plan_elements:
                try:
                    // Извлечение данных плана
                    name = self._extract_from_element(element, selectors['plan_name'])
                    price = self._extract_price(self._extract_from_element(element, selectors['price']))
                    data = self._extract_data_amount(self._extract_from_element(element, selectors['data']))
                    
                    // Дополнительная информация
                    additional_info = self._extract_additional_info(element)
                    
                    if name or price or data:
                        plan = MobilePlan(
                            name=name or "Не указано",
                            operator=analysis.name,
                            price=price or "Не указано", 
                            data=data or "Не указано",
                            additional_info=additional_info,
                            source_url=analysis.url
                        )
                        plans.append(plan)
                        logger.info(f"📱 План: {plan.name} - {plan.price}")
                        
                except Exception as e:
                    logger.debug(f"Ошибка парсинга элемента: {e}")
                    continue
                    
        except Exception as e:
            logger.error(f"Ошибка парсинга HTML для {analysis.name}: {e}")
        
        return plans

    def _extract_from_element(self, element, selectors: str) -> str:
        """Извлечение текста из элемента по селекторам"""
        for selector in selectors.split(', '):
            try:
                elem = element.select_one(selector.strip())
                if elem:
                    return self._clean_text(elem.get_text())
            except:
                continue
        return ""

    def _extract_additional_info(self, element) -> str:
        """Извлечение дополнительной информации о плане"""
        info_parts = []
        
        // Поиск информации о звонках и SMS
        text = element.get_text().lower()
        
        if any(word in text for word in ['ubegrenset samtaler', 'fri samtaler', 'unlimited calls']):
            info_parts.append("Безлимитные звонки")
        
        if any(word in text for word in ['ubegrenset sms', 'fri sms', 'unlimited sms']):
            info_parts.append("Безлимитные SMS")
        
        if any(word in text for word in ['5g', '5g-nett', '5g network']):
            info_parts.append("5G поддержка")
        
        return "; ".join(info_parts)

    async def parse_operator(self, operator_key: str) -> Tuple[List[MobilePlan], SiteAnalysis]:
        """Парсинг тарифов конкретного оператора"""
        logger.info(f"🚀 Парсинг {operator_key}")
        
        // Сначала анализируем структуру
        analysis = await self.analyze_site_structure(operator_key)
        self.site_analysis[operator_key] = analysis
        
        if analysis.status != 'success':
            logger.error(f"❌ Не удалось проанализировать {operator_key}")
            return [], analysis
        
        // Загружаем страницу для парсинга
        html = await self._fetch_with_retry(analysis.url)
        if not html:
            logger.error(f"❌ Не удалось загрузить {operator_key}")
            return [], analysis
        
        // Парсим планы
        plans = self._parse_plans_from_html(html, analysis)
        
        logger.info(f"✅ {operator_key}: найдено {len(plans)} планов")
        return plans, analysis

    async def parse_all_operators(self) -> List[MobilePlan]:
        """Параллельный парсинг всех операторов"""
        logger.info("🚀 Начинаем полный парсинг")
        
        tasks = [self.parse_operator(key) for key in self.operators_config.keys()]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        all_plans = []
        for i, result in enumerate(results):
            operator_key = list(self.operators_config.keys())[i]
            
            if isinstance(result, Exception):
                logger.error(f"❌ Ошибка {operator_key}: {result}")
            else:
                plans, analysis = result
                all_plans.extend(plans)
        
        self.plans = all_plans
        logger.info(f"🎉 Всего найдено {len(all_plans)} планов")
        return all_plans

    def save_results(self, filename: str = 'norway_mobile_plans.json'):
        """Сохранение результатов"""
        try:
            // Статистика по операторам
            operator_stats = {}
            for plan in self.plans:
                if plan.operator not in operator_stats:
                    operator_stats[plan.operator] = 0
                operator_stats[plan.operator] += 1
            
            data = {
                'metadata': {
                    'total_plans': len(self.plans),
                    'operators_found': list(operator_stats.keys()),
                    'operator_stats': operator_stats,
                    'parsing_analysis': {k: asdict(v) for k, v in self.site_analysis.items()}
                },
                'plans': [asdict(plan) for plan in self.plans]
            }
            
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            logger.info(f"💾 Результаты сохранены в {filename}")
            
        except Exception as e:
            logger.error(f"❌ Ошибка сохранения: {e}")

    def print_analysis_summary(self):
        """Вывод сводки анализа и результатов"""
        print(f"\n{'='*80}")
        print("📊 СВОДКА АНАЛИЗА И ПАРСИНГА")
        print(f"{'='*80}")
        
        // Анализ структуры сайтов
        print(f"\n🔍 АНАЛИЗ СТРУКТУРЫ САЙТОВ:")
        for key, analysis in self.site_analysis.items():
            print(f"\n📱 {analysis.name}:")
            print(f"   Статус: {analysis.status}")
            print(f"   Cookie баннер: {'Да' if analysis.has_cookie_banner else 'Нет'}")
            print(f"   Требует JS: {'Да' if analysis.requires_js else 'Нет'}")
            
            if analysis.plan_containers:
                best = analysis.plan_containers[0]
                print(f"   Лучший контейнер: {best['selector']} ({best['count']} элементов, уверенность: {best['confidence']:.2f})")
        
        // Результаты парсинга
        print(f"\n📊 РЕЗУЛЬТАТЫ ПАРСИНГА:")
        print(f"🎯 Всего найдено планов: {len(self.plans)}")
        
        if not self.plans:
            print("❌ Планы не найдены")
            return
        
        // Группировка по операторам
        by_operator = {}
        for plan in self.plans:
            if plan.operator not in by_operator:
                by_operator[plan.operator] = []
            by_operator[plan.operator].append(plan)
        
        for operator, plans in by_operator.items():
            print(f"\n📱 {operator}: {len(plans)} планов")
            for plan in plans[:3]:
                print(f"   • {plan.name} - {plan.price} - {plan.data}")
                if plan.additional_info:
                    print(f"     Доп. инфо: {plan.additional_info}")
            
            if len(plans) > 3:
                print(f"   ... и еще {len(plans) - 3} планов")

async def main():
    """Основная функция"""
    parser = argparse.ArgumentParser(description='Парсер норвежских мобильных тарифов')
    parser.add_argument('--operator', choices=['telia', 'telenor', 'ice', 'mycall'],
                       help='Парсить конкретного оператора')
    parser.add_argument('--analyze-only', action='store_true',
                       help='Только анализ структуры без парсинга')
    parser.add_argument('--output', '-o', default='norway_mobile_plans.json',
                       help='Файл для сохранения')
    parser.add_argument('--silent', '-s', action='store_true',
                       help='Минимальный вывод')
    
    args = parser.parse_args()
    
    if args.silent:
        logging.getLogger().setLevel(logging.WARNING)
    
    try:
        async with UnifiedNorwayMobileParser() as parser_instance:
            if args.analyze_only:
                // Только анализ структуры
                for key in parser_instance.operators_config.keys():
                    if not args.operator or args.operator == key:
                        await parser_instance.analyze_site_structure(key)
            else:
                // Полный парсинг
                if args.operator:
                    await parser_instance.parse_operator(args.operator)
                else:
                    await parser_instance.parse_all_operators()
                
                parser_instance.save_results(args.output)
            
            if not args.silent:
                parser_instance.print_analysis_summary()
                
    except KeyboardInterrupt:
        print("\n⏹️ Прервано пользователем")
    except Exception as e:
        logger.error(f"❌ Критическая ошибка: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())