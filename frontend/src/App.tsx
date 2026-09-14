import { Button } from './components/Button.tsx';
import { Input } from './components/Input.tsx';
import { FormField } from './components/Formfield.tsx';
import { IconButton } from './components/IconButton.tsx';
import { FileX, Trash2 } from 'lucide-react';
import { Checkbox } from './components/CheckBox.tsx';
import { OTPInput } from './components/OTPInput.tsx';
import { useEffect, useState } from 'react';
import { Avatar } from './components/Avatar.tsx';
import { Badge } from './components/Badge.tsx';
import { Modal, ModalContent, ModalTrigger } from './components/Modal.tsx';
import { ConfirmDialog } from './components/ConfirmDialog.tsx';
import { EmptyState } from './components/EmptyState.tsx';
import { DiagnosticCard } from './features/data/diagnostics/DiagnosticCard.tsx';
import { datasetApi } from './api';
import type { Diagnostic } from './api/types.ts';

// import { Dialog } from '@radix-ui/react-dialog';
function App() {
  const [code, setCode] = useState<string>('');
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [diagnostics, setDiagnostics] = useState<Diagnostic[]>([]);

  useEffect(() => {
    const loadDiagnostics = async () => {
      const data = await datasetApi.getDiagnostics('user-001');
      setDiagnostics(data);
    };

    loadDiagnostics();
  }, []);
  return (
    <>
      <Button>Create</Button>
      <Input type="email" placeholder="you@example.com" />
      <FormField label="Email" required>
        <Input type="email" />
      </FormField>
      <IconButton
        icon={<Trash2 size={16} />}
        aria-label="Remove profile"
        variant="danger"
        size="sm"
        // onClick={}
      />
      <Checkbox
        id="consent"
        label="I agree to share my records with this hospital"
        // checked={consented}
        // onChange={(e) => setConsented(e.target.checked)}
      />
      <OTPInput
        length={6}
        value={code}
        onChange={setCode}
        // onComplete={(fullCode) => verifyMfaCode(fullCode)}
      />
      <Avatar name={'Temciuc Adelina'} src={''} size="sm" />
      <Badge variant="neutral">Previous</Badge>
      <Badge variant="warning">Pending</Badge>
      <Badge variant="success">Connected</Badge>
      <Badge variant="danger">Revoked</Badge>
      <Badge variant="neutral">City Hospital</Badge>
      <Modal>
        <ModalTrigger asChild>
          <Button variant="primary">Connect hospital</Button>
        </ModalTrigger>
        <ModalContent
          title="Connect to City Hospital"
          description="CureVault will request your diagnostics and prescriptions using your IDNP. No other data is shared."
        >
          <div className="flex justify-end gap-3">
            {/*<Dialog.Close asChild>*/}
            <Button variant="ghost">Cancel</Button>
            {/*</Dialog.Close>*/}
            <Button variant="primary">I consent, connect</Button>
          </div>
        </ModalContent>
      </Modal>
      <ConfirmDialog
        open={confirmOpen}
        onOpenChange={setConfirmOpen}
        title="Revoke connection to City Hospital?"
        description="No further data will be pulled from this hospital. This can't be undone."
        confirmLabel="Revoke"
        variant="danger"
        // isLoading={isRevoking}
        onConfirm={() => console.log('Connection revoked')}
      />
      <EmptyState
        icon={<FileX size={32} />}
        title="No diagnostics yet"
        description="Diagnostics added by a connected hospital, or uploaded by you, will appear here."
      />
      <div>
        {diagnostics.map((diagnostic) => (
          <DiagnosticCard key={diagnostic.id} diagnostic={diagnostic} />
        ))}
      </div>{' '}
    </>
  );
}

export default App;
