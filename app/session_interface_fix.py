# Werkzeug 3+：set_cookie 的 value 须为 str；flask-session 0.5 + itsdangerous 在 SESSION_USE_SIGNER 下
# 可能得到 bytes，触发 TypeError: cannot use a string pattern on a bytes-like object
from itsdangerous import want_bytes

from flask_session.sessions import RedisSessionInterface, total_seconds


class BytesSafeRedisSessionInterface(RedisSessionInterface):
    """与 RedisSessionInterface 一致，仅在写入 Cookie 前将 session_id 转为 str。"""

    def save_session(self, app, session, response):
        domain = self.get_cookie_domain(app)
        path = self.get_cookie_path(app)
        if not session:
            if session.modified:
                self.redis.delete(self.key_prefix + session.sid)
                response.delete_cookie(
                    app.config["SESSION_COOKIE_NAME"], domain=domain, path=path
                )
            return

        conditional_cookie_kwargs = {}
        httponly = self.get_cookie_httponly(app)
        secure = self.get_cookie_secure(app)
        if self.has_same_site_capability:
            conditional_cookie_kwargs["samesite"] = self.get_cookie_samesite(app)
        expires = self.get_expiration_time(app, session)
        val = self.serializer.dumps(dict(session))
        self.redis.setex(
            name=self.key_prefix + session.sid,
            value=val,
            time=total_seconds(app.permanent_session_lifetime),
        )
        if self.use_signer:
            session_id = self._get_signer(app).sign(want_bytes(session.sid))
        else:
            session_id = session.sid
        if isinstance(session_id, bytes):
            session_id = session_id.decode("utf-8")
        response.set_cookie(
            app.config["SESSION_COOKIE_NAME"],
            session_id,
            expires=expires,
            httponly=httponly,
            domain=domain,
            path=path,
            secure=secure,
            **conditional_cookie_kwargs,
        )
