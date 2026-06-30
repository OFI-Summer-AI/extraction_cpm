"""Servicio para obtener carpetas de procesos desde Symbio Business Manager."""

from __future__ import annotations

import os
from collections import deque
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

import requests

DEFAULT_BASE_URL = "https://designer-dev.symbioweb.com"
DEFAULT_FACET = "Processes"
DEFAULT_FILTER = "stereoType -eq 'ProcessGroup'"
DEFAULT_PAGE_SIZE = 100
DEFAULT_FOLDER_TYPES = frozenset(
    {"subCategory", "processGroup", "category", "mainProcess"}
)
DEFAULT_MAX_WORKERS = 8


class SymbioProcessFoldersError(Exception):
    """Error al consultar carpetas de procesos en Symbio."""


def _resolve_auth_token(symbio_auth_token: str | None) -> str:
    token = symbio_auth_token or os.getenv("SYMBIO_AUTH_TOKEN")
    if not token:
        raise SymbioProcessFoldersError(
            "Debe proporcionar symbio_auth_token o definir la variable de entorno SYMBIO_AUTH_TOKEN."
        )
    return token


def _extract_values(payload: dict[str, Any]) -> list[dict[str, Any]]:
    data = payload.get("data")
    if isinstance(data, dict) and isinstance(data.get("values"), list):
        return data["values"]

    values = payload.get("values")
    if isinstance(values, list):
        return values

    raise SymbioProcessFoldersError(
        "La respuesta de la API no contiene un arreglo válido en 'data.values' ni en 'values'."
    )


def _extract_name(element: dict[str, Any]) -> str:
    properties = element.get("properties") or {}
    name = properties.get("name")
    if name:
        return str(name)

    for attribute in element.get("attributes") or []:
        if attribute.get("key") != "name":
            continue

        attribute_values = attribute.get("values") or []
        for item in attribute_values:
            if item.get("lcid") == 1033 and item.get("value"):
                return str(item["value"])

        if attribute_values and attribute_values[0].get("value"):
            return str(attribute_values[0]["value"])

    return ""


def _extract_type(element: dict[str, Any]) -> str | None:
    properties = element.get("properties") or {}
    element_type = properties.get("type")
    return str(element_type) if element_type else None


def _build_client(
    base_url: str,
    storagecollection: str,
    tenant: str,
    token: str,
    timeout: float,
) -> tuple[requests.Session, str]:
    session = requests.Session()
    session.headers.update(
        {
            "symbio-auth-token": token,
            "Accept": "application/json",
        }
    )

    elements_url = (
        f"{base_url.rstrip('/')}/"
        f"{storagecollection}/{tenant}/_api/v2/data/elements"
    )
    return session, elements_url


def _fetch_roots(
    session: requests.Session,
    elements_url: str,
    facet: str,
    filter_expression: str | None,
    page_size: int,
    timeout: float,
) -> list[dict[str, Any]]:
    params: dict[str, Any] = {
        "Facet": facet,
        "PageSize": page_size,
    }
    if filter_expression:
        params["Filter"] = filter_expression

    response = session.get(elements_url, params=params, timeout=timeout)
    response.raise_for_status()
    return _extract_values(response.json())


def _fetch_element(
    session: requests.Session,
    elements_url: str,
    element_id: str,
    facet: str,
    timeout: float,
) -> dict[str, Any]:
    response = session.get(
        f"{elements_url}/{element_id}",
        params={"Facet": facet},
        timeout=timeout,
    )
    response.raise_for_status()
    return response.json()


def _collect_folder_options_recursive(
    session: requests.Session,
    elements_url: str,
    facet: str,
    roots: list[dict[str, Any]],
    folder_types: frozenset[str],
    max_workers: int,
    timeout: float,
) -> list[dict[str, str]]:
    """
    Recorre el árbol de procesos.

    El endpoint /v2/data/elements solo devuelve nodos raíz (p. ej. 2 elementos).
    Las carpetas reales están anidadas en `children` y requieren consultar
    /v2/data/elements/{id} para expandir cada nivel.
    """
    pending: deque[str] = deque()
    visited: set[str] = set()
    folders: list[dict[str, str]] = []

    for root in roots:
        root_id = root.get("id")
        if root_id:
            pending.append(str(root_id))

    while pending:
        batch: list[str] = []
        while pending and len(batch) < max_workers * 4:
            element_id = pending.popleft()
            if element_id in visited:
                continue
            visited.add(element_id)
            batch.append(element_id)

        if not batch:
            continue

        fetched_elements: list[dict[str, Any]] = []
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(
                    _fetch_element,
                    session,
                    elements_url,
                    element_id,
                    facet,
                    timeout,
                ): element_id
                for element_id in batch
            }

            for future in as_completed(futures):
                element = future.result()
                fetched_elements.append(element)

        for element in fetched_elements:
            element_id = element.get("id")
            element_type = _extract_type(element)

            if element_id and element_type in folder_types:
                folders.append(
                    {
                        "id": str(element_id),
                        "name": _extract_name(element),
                    }
                )

            for child in element.get("children") or []:
                child_id = child.get("id")
                if child_id and str(child_id) not in visited:
                    pending.append(str(child_id))

    folders.sort(key=lambda item: (item["name"].lower(), item["id"]))
    return folders


def get_process_folder_options(
    storagecollection: str,
    tenant: str,
    symbio_auth_token: str | None = None,
    *,
    base_url: str = DEFAULT_BASE_URL,
    facet: str = DEFAULT_FACET,
    filter_expression: str | None = DEFAULT_FILTER,
    page_size: int = DEFAULT_PAGE_SIZE,
    folder_types: set[str] | frozenset[str] | None = None,
    recursive: bool = True,
    max_workers: int = DEFAULT_MAX_WORKERS,
    timeout: float = 60.0,
) -> list[dict[str, str]]:
    """
    Obtiene carpetas de procesos listas para un dropdown.

    Returns:
        Lista de objetos con forma: {"id": str, "name": str}
    """
    token = _resolve_auth_token(symbio_auth_token)
    selected_folder_types = frozenset(folder_types or DEFAULT_FOLDER_TYPES)

    try:
        session, elements_url = _build_client(
            base_url,
            storagecollection,
            tenant,
            token,
            timeout,
        )
        # El filtro ProcessGroup solo aplica al listado raíz y no devuelve todas las carpetas.
        # Para el modo recursivo se obtienen las raíces sin filtro y luego se expande el árbol.
        root_filter = None if recursive else filter_expression
        roots = _fetch_roots(
            session,
            elements_url,
            facet,
            root_filter,
            page_size,
            timeout,
        )

        if not recursive:
            return [
                {
                    "id": str(element["id"]),
                    "name": _extract_name(element),
                }
                for element in roots
                if element.get("id") and _extract_type(element) in selected_folder_types
            ]

        return _collect_folder_options_recursive(
            session,
            elements_url,
            facet,
            roots,
            selected_folder_types,
            max_workers,
            timeout,
        )
    except requests.RequestException as exc:
        raise SymbioProcessFoldersError(
            f"Error HTTP al consultar carpetas de procesos: {exc}"
        ) from exc
    except ValueError as exc:
        raise SymbioProcessFoldersError(
            "La respuesta de la API no es un JSON válido."
        ) from exc
    except SymbioProcessFoldersError:
        raise
    except Exception as exc:
        raise SymbioProcessFoldersError(
            f"Error inesperado al procesar carpetas de procesos: {exc}"
        ) from exc
