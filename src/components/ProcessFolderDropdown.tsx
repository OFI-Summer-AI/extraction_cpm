import { useProcessFolders } from '../hooks/useProcessFolders';
import { ProcessFolder } from '../services/symbioProcessFolders';

interface ProcessFolderDropdownProps {
  storagecollection: string;
  tenant: string;
  symbioAuthToken?: string;
  value?: string;
  onChange: (folder: ProcessFolder | null) => void;
  placeholder?: string;
  disabled?: boolean;
  className?: string;
  autoFetch?: boolean;
}

export function ProcessFolderDropdown({
  storagecollection,
  tenant,
  symbioAuthToken,
  value,
  onChange,
  placeholder = 'Seleccionar carpeta de proceso...',
  disabled = false,
  className = '',
  autoFetch = true,
}: ProcessFolderDropdownProps) {
  const { folders, loading, error, refetch } = useProcessFolders({
    storagecollection,
    tenant,
    symbioAuthToken,
    autoFetch,
  });

  const selectedFolder = folders.find((f) => f.id === value) || null;

  const handleChange = (event: React.ChangeEvent<HTMLSelectElement>) => {
    const folderId = event.target.value;
    if (!folderId) {
      onChange(null);
      return;
    }
    const folder = folders.find((f) => f.id === folderId) || null;
    onChange(folder);
  };

  return (
    <div className={className}>
      <select
        value={value || ''}
        onChange={handleChange}
        disabled={disabled || loading}
        aria-invalid={!!error}
        aria-describedby={error ? 'folder-error' : undefined}
      >
        <option value="" disabled>
          {loading ? 'Cargando...' : placeholder}
        </option>
        {folders.map((folder) => (
          <option key={folder.id} value={folder.id}>
            {folder.name}
          </option>
        ))}
      </select>

      {error && (
        <p id="folder-error" role="alert" style={{ color: 'red', fontSize: '0.875rem', marginTop: '0.25rem' }}>
          {error}
          <button type="button" onClick={refetch} style={{ marginLeft: '0.5rem' }}>
            Reintentar
          </button>
        </p>
      )}
    </div>
  );
}