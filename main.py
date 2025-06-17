# main.py
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

class NorwayMobileParser:
    """Оптимизированный парсер норвежских мобильных тарифов"""
    
    def __init__(self):
        self.session: Optional[aiohttp.ClientSession] = None
        self.plans: List[MobilePlan] = []
        
        # Конфигурация сайтов операторов
        self.operators_config = {
            'telia': {
                'url': 'https://www.telia.no/privat/mobil/abonnement',
                'name': 'Telia',
                'selectors': {
                    'plan_cards': '.product-card, .plan-card, [data-testid*="plan"], .subscription-card',
                    'plan_name': 'h3, .plan-name, .product-title, .subscription-name',
                    'price': '.price, .monthly-price, [data-testid*="price"]',
                    'data': '.data-amount, .gb-amount, [data-testid*="data"]'
                }
            },
            'telenor': {
                'url': 'https://www.telenor.no/privat/mobil/abonnement',
                'name': 'Telenor',
                'selectors': {
                    'plan_cards': '.product-card, .plan-item, .subscription-box, [data-cy*="plan"]',
                    'plan_name': 'h3, .plan-title, .product-name',
                    'price': '.price, .amount, [data-cy*="price"]',
                    'data': '.data-text, .gb-text, [data-cy*="data"]'
                }
            },
            'ice': {
                'url': 'https://www.ice.no/mobil/abonnement',
                'name': 'Ice',
                'selectors': {
                    'plan_cards': '.plan-card, .product-item, .subscription-container',
                    'plan_name': 'h3, .plan-name, .title',
                    'price': '.price, .cost, .monthly-fee',
                    'data': '.data-limit, .gb-limit, .data-info'
                }
            },
            'mycall': {
                'url': 'https://mycall.no/mobile-plans',
                'name': 'MyCall',
                'selectors': {
                    'plan_cards': '.plan-box, .offer-card, .mobile-plan',
                    'plan_name': 'h3, .plan-title',
                    'price': '.price, .monthly-price',
                    'data': '.data-amount, .gb-info'
                }
            }
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
        """Асинхронный контекст-менеджер - вход"""
        connector = aiohttp.TCPConnector(limit=10, limit_per_host=5, ttl_dns_cache=300)
        timeout = aiohttp.ClientTimeout(total=30, connect=10)
        self.session = aiohttp.ClientSession(
            headers=self.headers,
            connector=connector,
            timeout=timeout,
            cookie_jar=aiohttp.CookieJar(unsafe=True)
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Асинхронный контекст-менеджер - выход"""
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

    async def _fetch_page(self, url: str, max_retries: int = 3) -> Optional[str]:
        """Загрузка страницы с повторными попытками"""
        for attempt in range(max_retries):
            try:
                logger.info(f"🔄 Загрузка {url} (попытка {attempt + 1}/{max_retries})")
                
                async with self.session.get(url, allow_redirects=True) as response:
                    if response.status == 200:
                        content = await response.text()
                        logger.info(f"✅ Страница загружена успешно ({len(content)} символов)")
                        return content
                    else:
                        logger.warning(f"⚠️ HTTP {response.status} для {url}")
                        
            except asyncio.TimeoutError:
                logger.warning(f"⏱️ Таймаут для {url}")
            except Exception as e:
                logger.error(f"❌ Ошибка загрузки {url}: {e}")
                
            if attempt < max_retries - 1:
                await asyncio.sleep(2 ** attempt)  # Экспоненциальная задержка
        
        return None

    def _parse_operator_page(self, html: str, operator_config: Dict[str, Any], base_url: str) -> List[MobilePlan]:
        """Парсинг страницы конкретного оператора"""
        plans = []
        
        try:
            soup = BeautifulSoup(html, 'html.parser')
            selectors = operator_config['selectors']
            operator_name = operator_config['name']
            
            # Поиск карточек тарифов
            plan_elements = []
            for selector in selectors['plan_cards'].split(', '):
                elements = soup.select(selector.strip())
                plan_elements.extend(elements)
            
            logger.info(f"🔍 Найдено {len(plan_elements)} потенциальных карточек для {operator_name}")
            
            for element in plan_elements:
                try:
                    # Извлечение названия плана
                    name = ""
                    for name_selector in selectors['plan_name'].split(', '):
                        name_elem = element.select_one(name_selector.strip())
                        if name_elem:
                            name = self._clean_text(name_elem.get_text())
                            break
                    
                    # Извлечение цены
                    price = ""
                    for price_selector in selectors['price'].split(', '):
                        price_elem = element.select_one(price_selector.strip())
                        if price_elem:
                            price = self._extract_price(price_elem.get_text())
                            break
                    
                    # Извлечение данных
                    data = ""
                    for data_selector in selectors['data'].split(', '):
                        data_elem = element.select_one(data_selector.strip())
                        if data_elem:
                            data = self._extract_data_amount(data_elem.get_text())
                            break
                    
                    # Создание плана если есть основная информация
                    if name or price or data:
                        plan = MobilePlan(
                            name=name or "Не указано",
                            operator=operator_name,
                            price=price or "Не указано",
                            data=data or "Не указано",
                            source_url=base_url
                        )
                        plans.append(plan)
                        logger.info(f"📱 Найден план: {plan.name} - {plan.price}")
                
                except Exception as e:
                    logger.error(f"❌ Ошибка парсинга элемента: {e}")
                    continue
        
        except Exception as e:
            logger.error(f"❌ Ошибка парсинга страницы {operator_name}: {e}")
        
        return plans

    async def parse_operator(self, operator_key: str) -> List[MobilePlan]:
        """Парсинг тарифов конкретного оператора"""
        config = self.operators_config.get(operator_key)
        if not config:
            logger.error(f"❌ Неизвестный оператор: {operator_key}")
            return []
        
        logger.info(f"🚀 Парсинг тарифов {config['name']}")
        
        html = await self._fetch_page(config['url'])
        if not html:
            logger.error(f"❌ Не удалось загрузить страницу {config['name']}")
            return []
        
        plans = self._parse_operator_page(html, config, config['url'])
        logger.info(f"✅ Найдено {len(plans)} тарифов для {config['name']}")
        
        return plans

    async def parse_all_operators(self) -> List[MobilePlan]:
        """Парсинг всех операторов параллельно"""
        logger.info("🚀 Начинаем парсинг всех норвежских операторов")
        
        tasks = []
        for operator_key in self.operators_config.keys():
            task = self.parse_operator(operator_key)
            tasks.append(task)
        
        # Выполняем все задачи параллельно
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        all_plans = []
        for i, result in enumerate(results):
            operator_key = list(self.operators_config.keys())[i]
            if isinstance(result, Exception):
                logger.error(f"❌ Ошибка парсинга {operator_key}: {result}")
            else:
                all_plans.extend(result)
        
        self.plans = all_plans
        logger.info(f"🎉 Всего найдено {len(all_plans)} тарифных планов")
        
        return all_plans

    def save_to_json(self, filename: str = 'norway_mobile_plans.json'):
        """Сохранение результатов в JSON"""
        try:
            data = {
                'total_plans': len(self.plans),
                'operators': list(set(plan.operator for plan in self.plans)),
                'plans': [asdict(plan) for plan in self.plans],
                'timestamp': str(asyncio.get_event_loop().time())
            }
            
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            logger.info(f"💾 Результаты сохранены в {filename}")
            
        except Exception as e:
            logger.error(f"❌ Ошибка сохранения: {e}")

    def print_summary(self):
        """Вывод сводки результатов"""
        if not self.plans:
            print("❌ Тарифы не найдены")
            return
        
        print(f"\n📊 === СВОДКА РЕЗУЛЬТАТОВ ===")
        print(f"🎯 Всего найдено тарифов: {len(self.plans)}")
        
        # Группировка по операторам
        by_operator = {}
        for plan in self.plans:
            if plan.operator not in by_operator:
                by_operator[plan.operator] = []
            by_operator[plan.operator].append(plan)
        
        for operator, plans in by_operator.items():
            print(f"\n📱 {operator}: {len(plans)} тарифов")
            for plan in plans[:3]:  # Показываем первые 3 тарифа
                print(f"   • {plan.name} - {plan.price} - {plan.data}")
            if len(plans) > 3:
                print(f"   ... и еще {len(plans) - 3} тарифов")

async def main():
    """Основная функция"""
    parser = argparse.ArgumentParser(description='Парсер норвежских мобильных тарифов')
    parser.add_argument('--operator', choices=['telia', 'telenor', 'ice', 'mycall'], 
                       help='Парсить конкретного оператора')
    parser.add_argument('--output', '-o', default='norway_mobile_plans.json',
                       help='Файл для сохранения результатов')
    
    args = parser.parse_args()
    
    try:
        async with NorwayMobileParser() as mobile_parser:
            if args.operator:
                # Парсинг конкретного оператора
                plans = await mobile_parser.parse_operator(args.operator)
            else:
                # Парсинг всех операторов
                plans = await mobile_parser.parse_all_operators()
            
            # Сохранение и вывод результатов
            mobile_parser.save_to_json(args.output)
            mobile_parser.print_summary()
            
    except KeyboardInterrupt:
        print("\n⏹️ Парсинг прерван пользователем")
    except Exception as e:
        logger.error(f"❌ Критическая ошибка: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())