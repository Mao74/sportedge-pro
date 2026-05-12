import { useState } from 'react';
import {
  Button,
  Card,
  Chip,
  Drawer,
  Input,
  MetricCard,
  Modal,
  Segmented,
  Skeleton,
  Sparkline,
  Switch,
  useToast,
} from '@/components/primitives';

const SAMPLE_SPARK = [3, 5, 4, 7, 6, 9, 8, 11, 9, 13];

export default function PrimitivesDemo() {
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);
  const [seg, setSeg] = useState<'back' | 'lay'>('back');
  const [sw, setSw] = useState(false);
  const toast = useToast();

  return (
    <div className="space-y-8">
      <header>
        <div className="text-2xs uppercase tracking-widest text-text-tertiary">_dev</div>
        <h1 className="text-2xl font-medium text-text-primary">Primitives</h1>
        <p className="text-sm text-text-secondary">
          Reference gallery. Toggle theme from the sidebar to inspect both palettes.
        </p>
      </header>

      <Section title="Buttons">
        <div className="flex flex-wrap items-center gap-2">
          <Button variant="primary">Primary</Button>
          <Button variant="secondary">Secondary</Button>
          <Button variant="ghost">Ghost</Button>
          <Button variant="destructive">Destructive</Button>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Button size="sm">sm</Button>
          <Button size="md">md</Button>
          <Button size="lg">lg</Button>
          <Button size="xl">xl</Button>
          <Button loading>loading</Button>
          <Button disabled>disabled</Button>
        </div>
      </Section>

      <Section title="Chips">
        <div className="flex flex-wrap gap-2">
          <Chip>neutral</Chip>
          <Chip tone="gain" dot>+€41.20</Chip>
          <Chip tone="loss" dot>−€12.00</Chip>
          <Chip tone="warn">warning</Chip>
          <Chip tone="info">info</Chip>
          <Chip tone="brand" dot>strategy</Chip>
          <Chip tone="brand" onDismiss={() => {}}>dismissable</Chip>
        </div>
      </Section>

      <Section title="Inputs">
        <div className="grid max-w-md gap-3">
          <Input label="Email" name="email" placeholder="you@domain.tld" />
          <Input label="Stake (€)" name="stake" type="number" step="0.01" />
          <Input label="Errored" name="err" errorText="Required field" />
          <Input label="Hint" name="hint" hint="Hint text below the input" />
        </div>
      </Section>

      <Section title="Toggles">
        <Segmented
          options={[
            { value: 'back', label: 'Back' },
            { value: 'lay', label: 'Lay' },
          ]}
          value={seg}
          onChange={setSeg}
        />
        <Switch checked={sw} onChange={setSw} label="Lay 0-0 placed" />
      </Section>

      <Section title="Cards & metrics">
        <div className="grid gap-4 md:grid-cols-3">
          <MetricCard
            label="Bankroll"
            value="€2,847.00"
            delta="+€84.20 today"
            deltaTone="gain"
            spark={SAMPLE_SPARK}
            sparkTone="gain"
          />
          <MetricCard
            label="ROI"
            value="+12.4%"
            delta="−1.2% vs last week"
            deltaTone="loss"
            spark={SAMPLE_SPARK}
            sparkTone="loss"
          />
          <MetricCard
            label="Win rate"
            value="58.3%"
            delta="32 trades"
            deltaTone="zero"
            spark={SAMPLE_SPARK}
            sparkTone="info"
          />
        </div>
        <Card header={<span>Section card</span>} footer={<span>footer slot</span>}>
          <p className="text-sm text-text-secondary">
            Cards have hover-darken borders and 12px radius.
          </p>
        </Card>
      </Section>

      <Section title="Skeletons & sparkline">
        <div className="space-y-2">
          <Skeleton width={240} height={14} />
          <Skeleton width={180} height={14} />
          <Skeleton width={120} height={14} />
        </div>
        <div className="text-accent-brand">
          <Sparkline values={SAMPLE_SPARK} width={160} height={36} />
        </div>
      </Section>

      <Section title="Overlays">
        <div className="flex gap-2">
          <Button onClick={() => setDrawerOpen(true)}>Open drawer</Button>
          <Button onClick={() => setModalOpen(true)}>Open modal</Button>
          <Button onClick={() => toast.push({ tone: 'success', title: 'Saved.', description: 'Trade #1234 created.' })}>
            Toast: success
          </Button>
          <Button onClick={() => toast.push({ tone: 'error', title: 'Failed.', description: 'Network error.' })}>
            Toast: error
          </Button>
        </div>
      </Section>

      <Drawer open={drawerOpen} onClose={() => setDrawerOpen(false)} title="Drawer demo">
        <div className="space-y-3 text-sm text-text-secondary">
          <p>Right-side drawer, 480px width. Esc or backdrop closes.</p>
          <Input label="Some field" name="field" />
        </div>
      </Drawer>

      <Modal open={modalOpen} onClose={() => setModalOpen(false)} title="Modal demo">
        <p className="text-sm text-text-secondary">
          Centered modal with backdrop blur. Use sparingly.
        </p>
      </Modal>
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="space-y-3">
      <h2 className="text-sm font-medium uppercase tracking-widest text-text-tertiary">{title}</h2>
      <div className="space-y-3">{children}</div>
    </section>
  );
}
