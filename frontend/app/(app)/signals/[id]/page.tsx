import { Metadata } from "next";
import dynamic from "next/dynamic";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Signal Detail — Trading Intelligence",
};

const SignalDetailPageContent = dynamic(() => import("./SignalDetailPageContent"), { ssr: false });

export default function SignalDetailPage() {
  return <SignalDetailPageContent />;
}
