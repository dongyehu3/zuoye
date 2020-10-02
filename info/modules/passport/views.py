import re
import random
from datetime import datetime

from flask import current_app, jsonify, make_response, request, session

from info import constants, redis_client, db
from info.models import User
from info.utils.captcha.captcha import captcha
from info.utils.response_code import RET
from info.lib.yuntongxun.sms import CCP
from . import passport_bp


@passport_bp.route('/image_code')
def get_image_code():
    """
    获取验证码图片
    """

    # 1，获取当前图片id
    code_id = request.args.get('code_id')
    # 2, 生成验证码
    name, text, image = captcha.generate_captcha()
    try:
        redis_client.setex('ImageCode:' + code_id, constants.IMAGE_CODE_REDIS_EXPIRES, text)
    except Exception as e:
        current_app.logger.error(e)
        return make_response(jsonify(error=RET.DATAERR, errmsg='保存图片验证码失败'))

    # 返回响应内容
    resp = make_response(image)
    resp.headers['Content-Type'] = 'image/jpg'
    return resp


@passport_bp.route('/smscode', methods=['POST'])
def send_sms():
    """

       3. 通过传入的图片编码去redis中查询真实的图片验证码内容
       4. 进行验证码内容的比对
       5. 生成发送短信的内容并发送短信
       6. redis中保存短信验证码内容
       7. 返回发送成功的响应
       :return:
    """
    # 1. 接收参数并判断是否有值
    mobile = request.json.get('mobile')
    image_code = request.json.get('image_code')
    image_code_id = request.json.get('image_code_id')

    if not all([mobile, image_code, image_code_id]):
        return jsonify(error=RET.PARAMERR, errmsg='参数不全')

    # 2. 校验手机号是正确
    if not re.match("^1[3578][0-9]{9}$", mobile):
        # 提示手机号不正确
        return jsonify(errno=RET.DATAERR, errmsg="手机号不正确")

    # 3.通过传入的图片编码去redis中查询真实的图片验证码内容
    try:
        real_image_code = redis_client.get('ImageCode:' + image_code_id)
        if real_image_code:
            redis_client.delete('ImageCode:' + image_code_id)
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(error=RET.DBERR, errmsg='获取图片验证码失败')
    # 判断验证码是否已过期
    if not real_image_code:
        return jsonify(error=RET.NODATA, errmsg="验证码已过期")

    # 4, 检验该手机是否已注册
    try:
        user = User.query.filter(User.mobile==mobile).first()
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(error=RET.DBERR, errmsg="数据库查询错误")
    if user:
        return jsonify(errno=RET.DATAEXIST, errmsg="该手机已被注册")

    # 5,生成短信内容并验证
    result = random.randint(0, 999999)
    sms_code = '%06d' % result
    current_app.logger.debug('短信验证码的内容：%s' % sms_code)
    result = CCP().send_template_sms(mobile,  [sms_code, constants.SMS_CODE_REDIS_EXPIRES / 60], "1")

    # TODO 没用容联云 先注释了保证验证码可以保存
    # if result != 0:
    #     return jsonify(errno=RET.THIRDERR, errmsg="发送短信失败")

    # 6. redis中保存短信验证码内容
    try:
        redis_client.set("SMS_" + mobile, sms_code, constants.SMS_CODE_REDIS_EXPIRES)
    except Exception as e:
        current_app.logger.error(e)
        # 保存短信验证码失败
        return jsonify(errno=RET.DBERR, errmsg="保存短信验证码失败")

    # 7. 返回发送成功的响应
    return jsonify(errno=RET.OK, errmsg="发送成功")


@passport_bp.route('/register', methods=['POST'])
def reigster():
    """
    注册
    """

    # 1，判断参数是否有值
    mobile = request.json.get('mobile')
    smscode = request.json.get('smscode')
    password = request.json.get('password')

    if not all([mobile, smscode, password]):
        return jsonify(error=RET.PARAMERR, errmsg="参数不全")

    # 2, 从redis中获取指定手机号对应的短信验证码的
    try:
        real_sms_code = redis_client.get('SMS_' + mobile)
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(error=RET.DBERR, errmsg="获取本地验证码失败")

    if not real_sms_code:
        return jsonify(errno=RET.NODATA, errmsg="短信验证码过期")

    # 3, 校验验证码
    if smscode != real_sms_code:
        return jsonify(errno=RET.DATAERR, errmsg="短信验证码错误")
    # 删除
    try:
        redis_client.delete('SMS_' + mobile)
    except Exception as e:
        current_app.logger.error(e)

    user = User()
    user.mobile = mobile
    user.nick_name = mobile
    user.password = password

    try:
        db.session.add(user)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(e)
        return jsonify(errno=RET.DATAERR, errmsg="数据保存错误")

    # 5. 保存用户登录状态
    session.user_id = user.id
    session.nick_name= user.nick_name
    session.mobile = user.mobile

    # 6, 返回注册结果
    return jsonify(errno=RET.OK, errmsg="OK")


@passport_bp.route('/login', methods=['POST'])
def login():
    """
    登录
    """

    # 1,接受校验参数
    mobile = request.json.get('mobile')
    password = request.json.get('password')

    if not all([mobile, password]):
        return jsonify(errno=RET.PARAMERR, errmsg="参数不全")

    # 2,查数据库，校验是否存在
    try:
        user = User.query.filter(User.mobile==mobile).first()
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(error=RET.DBERR, errmsg="查询数据错误")

    if not user:
        return jsonify(errno=RET.USERERR, errmsg="用户不存在")

    # 3，校验密码
    if not user.check_password(password):
        return jsonify(errno=RET.PWDERR, errmsg="密码错误")

    # 4, 保存用户登陆状态
    session['user_id'] = user.id
    session['nick_name'] = user.nick_name
    session['mobile'] = user.mobile
    # 记录用户最后登录时间
    user.last_login = datetime.now()

    try:
        db.session.commit()
    except Exception as e:
        current_app.logger.error(e)
        # 5. 登录成功
    return jsonify(errno=RET.OK, errmsg="OK")


@passport_bp.route('/logout', methods=['POST'])
def logout():
    """
    清除session中的用户信息
    """

    session.pop('user_id', None)
    session.pop('nick_name', None)
    session.pop('mobile', None)

    return jsonify(error=RET.OK, errmsg="OK")