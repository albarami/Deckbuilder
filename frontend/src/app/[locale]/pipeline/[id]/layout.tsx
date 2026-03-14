/**
 * Pipeline session layout — wraps the pipeline view with
 * a progress sidebar (StageTracker) and main content area.
 */

export default function PipelineLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <>{children}</>;
}
