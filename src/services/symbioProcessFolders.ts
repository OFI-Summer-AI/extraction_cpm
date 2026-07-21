const SYMBIO_BASE_URL = 'https://designer-dev.symbioweb.com';

export interface ProcessFolder {
  id: string;
  name: string;
}

export class SymbioProcessFoldersError extends Error {
  constructor(
    message: string,
    public readonly status?: number,
    public readonly originalError?: Error
  ) {
    super(message);
    this.name = 'SymbioProcessFoldersError';
  }
}

interface SymbioApiResponse {
  data: {
    values: SymbioElement[];
  };
}

interface SymbioElement {
  id: string;
  properties: {
    name: string;
  };
}

export async function getProcessFolders(
  storagecollection: string,
  tenant: string,
  symbioAuthToken?: string
): Promise<ProcessFolder[]> {
  const token = symbioAuthToken ?? process.env.SYMBIO_AUTH_TOKEN ?? import.meta.env?.VITE_SYMBIO_AUTH_TOKEN;

  if (!token) {
    throw new SymbioProcessFoldersError(
      'Token de autenticación de Symbio no proporcionado. Pásalo como argumento o configura SYMBIO_AUTH_TOKEN / VITE_SYMBIO_AUTH_TOKEN.'
    );
  }

  const url = new URL(
    `${SYMBIO_BASE_URL}/${storagecollection}/${tenant}/_api/v2/data/elements`
  );
  url.searchParams.set('Facet', 'Processes');
  url.searchParams.set('Filter', "stereoType -eq 'ProcessGroup'");
  url.searchParams.set('PageSize', '100');

  try {
    const response = await fetch(url.toString(), {
      method: 'GET',
      headers: {
        'symbio-auth-token': token,
        Accept: 'application/json',
        'Content-Type': 'application/json',
      },
    });

    if (!response.ok) {
      const errorText = await response.text().catch(() => 'Sin detalles');
      throw new SymbioProcessFoldersError(
        `Error ${response.status} al obtener carpetas de procesos: ${errorText}`,
        response.status
      );
    }

    const data = (await response.json()) as SymbioApiResponse;

    if (!data.data?.values || !Array.isArray(data.data.values)) {
      throw new SymbioProcessFoldersError('Respuesta de la API inválida: se esperaba data.values array');
    }

    return data.data.values
      .filter((element): element is SymbioElement => element && typeof element.id === 'string' && element.properties?.name)
      .map((element) => ({
        id: element.id,
        name: element.properties.name,
      }));
  } catch (error) {
    if (error instanceof SymbioProcessFoldersError) {
      throw error;
    }
    throw new SymbioProcessFoldersError(
      `Error de red o parsing al obtener carpetas de procesos: ${error instanceof Error ? error.message : String(error)}`,
      undefined,
      error instanceof Error ? error : undefined
    );
  }
}