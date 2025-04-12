import functools
from json import JSONDecodeError
from typing import (Any, Callable, List, Literal, Optional, ParamSpec,
                    Sequence, Type, TypeVar, Union, overload)

from pydantic import BaseModel
from requests import Response

from .exceptions import KeycloakError

T = TypeVar('T', bound=BaseModel)
P = ParamSpec('P')


@overload
def result_or_error(
        response_model: Type[T], is_list: Literal[False] = ...
) -> Callable[[Callable[P, Union[Response, T]]], Callable[P, T]]:
    ...


@overload
def result_or_error(
        response_model: Type[T], is_list: Literal[True] = ...
) -> Callable[[Callable[P, Union[Response, T]]], Callable[P, Sequence[T]]]:
    ...


@overload
def result_or_error(
        response_model: Literal[None] = None, is_list: bool = False
) -> Callable[[Callable[P, Union[Response, Any]]], Callable[P, Any]]:
    ...


# FIXME
def result_or_error(  # type: ignore
        response_model: Optional[Type[T]] = None, is_list: bool = False
) -> Callable[[Callable[P, Union[Response, T]]], Callable[P, Union[T, List[T], Any]]]:
    """Decorator used to ease the handling of responses from Keycloak.

    Args:
        response_model (Type[BaseModel]): Object that should be returned based on the payload
        is_list (bool): True if the return value should be a list of the response model provided

    Returns:
        BaseModel or List[BaseModel]: Based on the given signature and response circumstances

    Raises:
        KeycloakError: If the resulting response is not a successful HTTP-Code (>299)

    Notes:
        - Keycloak sometimes returns empty payloads but describes the error in its content (byte encoded)
          which is why this function checks for JSONDecode exceptions.
        - Keycloak often does not expose the real error for security measures. You will most likely encounter:
          {'error': 'unknown_error'} as a result. If so, please check the logs of your Keycloak instance to get error
          details, the RestAPI doesn't provide any.
    """

    def inner(f: Callable[P, Union[Response, T]]) -> Callable[P, Union[List[T], T, Any]]:
        @functools.wraps(f)
        def wrapper(*args: P.args, **kwargs: P.kwargs):
            result: Union[Response, T] = f(*args, **kwargs)  # The actual call

            if not isinstance(result, Response):
                # If the object given is not a response object, directly return it.
                return result

            if result.status_code in range(100, 299):  # Successful
                if response_model is None:  # No model given

                    try:
                        return result.json()
                    except JSONDecodeError:
                        return result.content.decode("utf-8")

                else:  # Response model given
                    if is_list:
                        return [response_model.parse_obj(entry) for entry in result.json()]
                    else:
                        return response_model.parse_obj(result.json())

            else:  # Not Successful, forward status code and error
                try:
                    raise KeycloakError(
                        status_code=result.status_code, reason=result.json()
                    )
                except JSONDecodeError:
                    raise KeycloakError(
                        status_code=result.status_code,
                        reason=result.content.decode("utf-8"),
                    )

        return wrapper

    return inner
