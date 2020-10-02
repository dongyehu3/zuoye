import logging

from redis import StrictRedis


class BaseConfig():

    SECRET_KEY = "EjpNVSNQTyGi1VvWECj9TvC/+kq3oujee2kTfQUs8yCM6xX9Yjq52v54g+HVoknA"

    # mysql 配置
    SQLALCHEMY_DATABASE_URI = 'mysql://root:mysql@localhost/zuoye'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ECHO = False

    # redis 配置
    REDIS_HOST = 'localhost'
    REDIS_PORT = 6381

    # session配置
    SESSION_TYPE = 'redis'
    SESSION_REDIS = StrictRedis(host='localhost', port=6381)
    SESSION_USE_SIGNER = True
    PERMANENT_SESSION_LIFETIME = 3600

    # 日志配置
    LOG_LEVEL = logging.DEBUG


class DevConfig(BaseConfig):
    DEBUG = True
    LOG_LEVEL = logging.DEBUG

class ProConfig(BaseConfig):
    DEBUG = False


config_dict = {
    'dev': DevConfig,
    'pro': ProConfig
}