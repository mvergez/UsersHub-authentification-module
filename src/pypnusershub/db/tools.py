# coding: utf8

from __future__ import unicode_literals, print_function, absolute_import, division

"""
    DB tools not related to any model in particular.
"""
import logging
from datetime import datetime, timedelta

from flask import current_app

from sqlalchemy.orm.exc import NoResultFound
import sqlalchemy as sa
from authlib.jose import JsonWebToken
from authlib.jose.errors import ExpiredTokenError, JoseError

from pypnusershub.db import models
from pypnusershub.utils import text_resource_stream, get_current_app_id

log = logging.getLogger(__name__)


class AccessRightsError(Exception):
    pass


class InsufficientRightsError(AccessRightsError):
    pass


class AccessRightsExpiredError(AccessRightsError):
    pass


class UnreadableAccessRightsError(AccessRightsError):
    pass


class NoPasswordError(Exception):
    pass


class DifferentPasswordError(Exception):
    pass


# def init_schema(con_uri):

#     with text_resource_stream('schema.sql', 'pypnusershub.db') as sql_file:
#         sql = sql_file.read()

#     engine = sa.create_engine(con_uri)
#     with engine.connect():
#         engine.execute(sql)
#         engine.execute("COMMIT")


# def delete_schema(con_uri):

#     engine = sa.create_engine(con_uri)
#     with engine.connect():
#         engine.execute("DROP SCHEMA IF EXISTS utilisateurs CASCADE")
#         engine.execute("COMMIT")


# def reset_schema(con_uri):
#     delete_schema(con_uri)
#     init_schema(con_uri)


def load_fixtures(con_uri):
    with text_resource_stream("fixtures.sql", "pypnusershub.db") as sql_file:

        engine = sa.create_engine(con_uri)
        with engine.connect():
            for line in sql_file:
                if line.strip():
                    engine.execute(line)
            engine.execute("COMMIT")

def encode_token(payload):
    expire = datetime.now() + timedelta(seconds=current_app.config['COOKIE_EXPIRATION'])
    header = {
        "alg": "HS256",
        "exp": str(int(datetime.timestamp(expire))),
    }
    jwt = JsonWebToken(["HS256"])
    key = current_app.config['SECRET_KEY'].encode("UTF-8")
    return jwt.encode(header, payload, key)


def decode_token(payload):
    jwt = JsonWebToken(["HS256"])
    key = current_app.config['SECRET_KEY'].encode("UTF-8")
    claims = jwt.decode(payload, key)
    claims.validate()
    return dict(claims)


def user_to_token(user):
    return encode_token(user.as_dict())


def user_from_token(token, secret_key=None):
    """Given a, authentification token, return the matching AppUser instance"""

    secret_key = secret_key or current_app.config["SECRET_KEY"]

    try:
        data = decode_token(token)

        id_role = data["id_role"]
        id_app = data["id_application"]
        id_app_from_config = get_current_app_id()
        # check that the id_app from the token well corespond to the current_app id_application
        # for prevent conflit of token between applications on the same domain
        # if no ID_APP is passed to the app config, we don't check the conformiity of the token
        # for retro-compatibility reasons
        if id_app_from_config:
            if id_app != id_app_from_config:
                log.info("Invalid token: the token not corespoding to the current app")
                raise UnreadableAccessRightsError("Token BadSignature", 403)
        return (
            models.AppUser.query.filter(models.AppUser.id_role == id_role)
            .filter(models.AppUser.id_application == id_app)
            .one()
        )

    except NoResultFound:
        raise UnreadableAccessRightsError(
            'No user withd id "{}" for app "{}"'.format(id_role, id_app)
        )
    except ExpiredTokenError:
        raise AccessRightsExpiredError("Token expired")

    except JoseError:
        raise UnreadableAccessRightsError("Invalid token", 403)
