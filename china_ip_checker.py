# china_ip_checker.py
import geoip2.database
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Union, Optional, Set
from functools import lru_cache
import os
import logging

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ChinaIPChecker:
    """中国IP检查工具类"""

    # 默认配置
    DEFAULT_CONFIG = {
        'db_path': 'GeoLite2-Country.mmdb',
        'max_workers': 20,
        'cache_size': 10000,
        'timeout': 30
    }

    def __init__(self, **kwargs):
        """
        初始化检查器

        Args:
            db_path: 数据库路径
            max_workers: 最大并发数
            cache_size: 缓存大小
            timeout: 查询超时时间
        """
        self.config = {**self.DEFAULT_CONFIG, **kwargs}

        # 验证数据库文件
        if not os.path.exists(self.config['db_path']):
            raise FileNotFoundError(f"数据库文件不存在: {self.config['db_path']}")

        self.db_path = self.config['db_path']
        self._lock = threading.Lock()

        # 初始化缓存查询方法
        self._cached_query = lru_cache(maxsize=self.config['cache_size'])(self._query_database)

        logger.info(f"ChinaIPChecker 初始化完成，数据库: {self.db_path}")

    def _query_database(self, ip: str) -> tuple:
        """内部数据库查询方法"""
        try:
            with geoip2.database.Reader(self.db_path) as reader:
                response = reader.country(ip)
                return (response.country.iso_code, None)
        except geoip2.errors.AddressNotFoundError:
            return (None, 'IP地址未找到')
        except Exception as e:
            logger.warning(f"查询IP {ip} 时出错: {str(e)}")
            return (None, str(e))

    def _is_china_ip_single(self, ip: str) -> Dict[str, Union[str, bool]]:
        """单个IP查询"""
        result = {
            'ip': ip,
            'is_china': False,
            'country_code': None,
            'error': None,
            'cached': False
        }

        try:
            # 获取缓存信息
            cache_info_before = self._cached_query.cache_info()
            country_code, error = self._cached_query(ip)
            cache_info_after = self._cached_query.cache_info()

            # 判断是否命中缓存
            if cache_info_after.hits > cache_info_before.hits:
                result['cached'] = True

            result['country_code'] = country_code
            result['error'] = error
            result['is_china'] = country_code == 'CN' if country_code else False

        except Exception as e:
            result['error'] = f"查询异常: {str(e)}"
            logger.error(f"查询IP {ip} 异常: {str(e)}")

        return result

    def check_single(self, ip: str, use_cache: bool = True) -> Dict[str, Union[str, bool]]:
        """
        查询单个IP是否为中国IP

        Args:
            ip: IP地址
            use_cache: 是否使用缓存

        Returns:
            dict: 查询结果
        """
        if not use_cache:
            self._cached_query.cache_clear()

        return self._is_china_ip_single(ip)

    def check_batch(self, ips: List[str], max_workers: Optional[int] = None, use_cache: bool = True) -> List[
        Dict[str, Union[str, bool]]]:
        """
        批量查询IP是否为中国IP

        Args:
            ips: IP地址列表
            max_workers: 最大并发线程数
            use_cache: 是否使用缓存

        Returns:
            list: 查询结果列表
        """
        if not ips:
            return []

        # 去重处理
        unique_ips = list(dict.fromkeys(ips))  # 保持顺序的去重
        max_workers = max_workers or self.config['max_workers']

        if not use_cache:
            self._cached_query.cache_clear()

        results = []

        # 单个IP直接查询
        if len(unique_ips) == 1:
            return [self._is_china_ip_single(unique_ips[0])]

        # 批量并发查询
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_ip = {
                executor.submit(self._is_china_ip_single, ip): ip
                for ip in unique_ips
            }

            for future in as_completed(future_to_ip):
                try:
                    result = future.result(timeout=self.config['timeout'])
                    results.append(result)
                except Exception as e:
                    ip = future_to_ip[future]
                    results.append({
                        'ip': ip,
                        'is_china': False,
                        'country_code': None,
                        'error': f'查询超时或异常: {str(e)}',
                        'cached': False
                    })

        # 按原始顺序排序
        ip_order = {ip: index for index, ip in enumerate(unique_ips)}
        results.sort(key=lambda x: ip_order.get(x['ip'], float('inf')))

        return results

    def filter_china_ips(self, ips: List[str], use_cache: bool = True) -> List[str]:
        """
        筛选中国IP列表

        Args:
            ips: IP地址列表
            use_cache: 是否使用缓存

        Returns:
            list: 中国IP列表
        """
        results = self.check_batch(ips, use_cache=use_cache)
        return [result['ip'] for result in results if result['is_china'] and not result['error']]

    def filter_foreign_ips(self, ips: List[str], use_cache: bool = True) -> List[str]:
        """
        筛选非中国IP列表

        Args:
            ips: IP地址列表
            use_cache: 是否使用缓存

        Returns:
            list: 非中国IP列表
        """
        results = self.check_batch(ips, use_cache=use_cache)
        return [result['ip'] for result in results if not result['is_china'] and not result['error']]

    def get_statistics(self, ips: List[str], use_cache: bool = True) -> Dict[str, Union[int, float]]:
        """
        获取IP统计信息

        Args:
            ips: IP地址列表
            use_cache: 是否使用缓存

        Returns:
            dict: 统计信息
        """
        results = self.check_batch(ips, use_cache=use_cache)

        total = len(results)
        china_count = sum(1 for r in results if r['is_china'] and not r['error'])
        foreign_count = sum(1 for r in results if not r['is_china'] and not r['error'])
        error_count = sum(1 for r in results if r['error'])
        cached_count = sum(1 for r in results if r['cached'])

        return {
            'total': total,
            'china_ips': china_count,
            'foreign_ips': foreign_count,
            'error_ips': error_count,
            'cached_ips': cached_count,
            'china_percentage': round(china_count / total * 100, 2) if total > 0 else 0,
            'cache_hit_rate': round(cached_count / total * 100, 2) if total > 0 else 0
        }

    def clear_cache(self):
        """清除查询缓存"""
        self._cached_query.cache_clear()

    def get_cache_info(self) -> Dict[str, int]:
        """获取缓存信息"""
        info = self._cached_query.cache_info()
        return {
            'hits': info.hits,
            'misses': info.misses,
            'maxsize': info.maxsize,
            'currsize': info.currsize
        }

    def update_database(self, new_db_path: str):
        """
        更新数据库文件

        Args:
            new_db_path: 新数据库路径
        """
        if not os.path.exists(new_db_path):
            raise FileNotFoundError(f"新数据库文件不存在: {new_db_path}")

        self.db_path = new_db_path
        self.clear_cache()
        logger.info(f"数据库已更新为: {new_db_path}")


# 全局单例模式
_china_ip_checker = None
_checker_lock = threading.Lock()


def get_china_ip_checker(**kwargs) -> ChinaIPChecker:
    """
    获取ChinaIPChecker单例实例

    Args:
        **kwargs: 初始化参数

    Returns:
        ChinaIPChecker: 检查器实例
    """
    global _china_ip_checker

    with _checker_lock:
        if _china_ip_checker is None:
            _china_ip_checker = ChinaIPChecker(**kwargs)
        return _china_ip_checker


# 便捷函数
def is_china_ip(ip: str, db_path: str = None) -> bool:
    """
    快速检查单个IP是否为中国IP

    Args:
        ip: IP地址
        db_path: 数据库路径（可选）

    Returns:
        bool: 是否为中国IP
    """
    try:
        if db_path:
            checker = ChinaIPChecker(db_path=db_path)
        else:
            checker = get_china_ip_checker()

        result = checker.check_single(ip)
        return result['is_china'] and not result['error']
    except Exception as e:
        logger.error(f"检查IP {ip} 时出错: {str(e)}")
        return False


def filter_china_ips(ips: List[str], db_path: str = None) -> List[str]:
    """
    快速筛选中国IP列表

    Args:
        ips: IP地址列表
        db_path: 数据库路径（可选）

    Returns:
        list: 中国IP列表
    """
    try:
        if db_path:
            checker = ChinaIPChecker(db_path=db_path)
        else:
            checker = get_china_ip_checker()

        return checker.filter_china_ips(ips)
    except Exception as e:
        logger.error(f"筛选中国IP时出错: {str(e)}")
        return []


def get_ip_statistics(ips: List[str], db_path: str = None) -> Dict[str, Union[int, float]]:
    """
    获取IP统计信息

    Args:
        ips: IP地址列表
        db_path: 数据库路径（可选）

    Returns:
        dict: 统计信息
    """
    try:
        if db_path:
            checker = ChinaIPChecker(db_path=db_path)
        else:
            checker = get_china_ip_checker()

        return checker.get_statistics(ips)
    except Exception as e:
        logger.error(f"获取统计信息时出错: {str(e)}")
        return {}


# 批量查询函数
def batch_check_ips(ips: List[str], db_path: str = None, **kwargs) -> List[Dict[str, Union[str, bool]]]:
    """
    批量查询IP信息

    Args:
        ips: IP地址列表
        db_path: 数据库路径（可选）
        **kwargs: 其他参数

    Returns:
        list: 查询结果列表
    """
    try:
        if db_path:
            checker = ChinaIPChecker(db_path=db_path, **kwargs)
        else:
            checker = get_china_ip_checker(**kwargs)

        return checker.check_batch(ips)
    except Exception as e:
        logger.error(f"批量查询IP时出错: {str(e)}")
        return []


# 上下文管理器
class ChinaIPCheckerContext:
    """ChinaIPChecker上下文管理器"""

    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.checker = None

    def __enter__(self):
        self.checker = ChinaIPChecker(**self.kwargs)
        return self.checker

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.checker:
            self.checker.clear_cache()


# 装饰器
def china_ip_required(func):
    """装饰器：确保函数参数中的IP为中国IP"""

    def wrapper(*args, **kwargs):
        # 简单示例，实际使用时需要根据具体业务调整
        checker = get_china_ip_checker()
        # 这里可以根据需要检查参数中的IP
        return func(*args, **kwargs)

    return wrapper
