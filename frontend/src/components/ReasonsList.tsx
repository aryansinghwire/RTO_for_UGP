export default function ReasonsList({ reasons }: { reasons: string[] }) {
  return (
    <ul className="list-disc space-y-1 pl-4 text-sm text-neutral-700 dark:text-neutral-300">
      {reasons.map((r) => (
        <li key={r}>{r}</li>
      ))}
    </ul>
  );
}
