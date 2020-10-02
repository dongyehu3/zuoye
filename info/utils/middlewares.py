from flask_wtf.csrf import generate_csrf


def create_csrf(response):
    """
    生成csrftoken，并加到响应对象的cookie
    """
    csrf_token = generate_csrf()
    response.set_cookie("csrf_token", csrf_token)
    return response

