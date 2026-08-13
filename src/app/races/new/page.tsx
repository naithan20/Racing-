import { NewRaceForm } from "@/components/races/NewRaceForm";

export default function NewRacePage() {
  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-6">
      <div>
        <h1 className="text-lg font-semibold text-text-primary">Manual race creation</h1>
        <p className="mt-1 text-sm text-text-secondary">
          Create a race and its runners by hand. For bulk entry, use CSV or JSON import instead — see the{" "}
          <a href="/import" className="text-accent hover:underline">
            Import
          </a>{" "}
          page.
        </p>
      </div>
      <NewRaceForm />
    </div>
  );
}
