"""数据访问层 - 封装基金数据采集、缓存、限流与失败降级。

下游所有业务模块只依赖 `DataProvider` 抽象接口。
"""

from src.data.config import DataConfig, load_data_config, setup_logging
from src.data.provider import DataProvider, FundCategory

__all__ = ["DataConfig", "load_data_config", "setup_logging", "DataProvider", "FundCategory"]
