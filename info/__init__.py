import logging
from logging.handlers import RotatingFileHandler

from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_session import Session
from flask_wtf.csrf import CSRFProtect
from redis import StrictRedis

from settings.config import config_dict
from settings import constants

db = SQLAlchemy()
redis_client = None



def setup_log(config_type):
    """
    配置日志
    """

    # 设置日志记录等级
    logging.basicConfig(level=config_dict[config_type].LOG_LEVEL)
    # 创建日志记录器，指明日志保存路径，每个文件大小，个数上限
    file_log_handler = RotatingFileHandler('logs/log', maxBytes=1024*1024*100, backupCount=10)
    # 创建日志记录格式 等级， 输入日志信息文件名 行数，日志信息
    formatter = logging.Formatter('%(levelname)s %(filename)s:%(lineno)d %(message)s')
    # 为刚创建的日志记录器设置日志记录格式
    file_log_handler.setFormatter(formatter)
    # 为全局的日志工具对象添加日志记录器
    logging.getLogger().addHandler(file_log_handler)


def register_blueprint(app):
    """
    注册蓝图
    """

    from info.modules.index import index_bp
    app.register_blueprint(index_bp)
    from info.modules.passport import passport_bp
    app.register_blueprint(passport_bp)


def register_app(app):
    """
    注册组件
    """

    # mysql
    from info import db
    db.init_app(app)

    # redis
    global redis_client
    redis_client = StrictRedis(host=app.config['REDIS_HOST'], port=app.config['REDIS_PORT'], db=1, decode_responses=True)

    # 添加请求before_request
    from info.utils import middlewares
    app.after_request(middlewares.create_csrf)

    # session
    Session(app)
    # csrf保护
    # CSRFProtect(app)
    # 迁移模型组件
    Migrate(app, db)

    from info import models


def load_config_app(app, config_type):
    """
    加载配置
    """

    app.config.from_object(config_dict[config_type])
    app.config.from_envvar(constants.EXTRA_ENV_CONFIG, silent=True)


def  create_app(config_type):
    """
    初始化app，加载配置，注册组件，蓝图
    """

    # 配置项目日志
    setup_log(config_type)

    app = Flask(__name__)

    # 加载配置
    load_config_app(app, config_type)
    # 注册组件
    register_app(app)
    # 注册蓝图
    register_blueprint(app)


    return app


