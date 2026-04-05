import { SidebarWrapper } from "@/components/SidebarWrapper";
import { SessionProvider } from "next-auth/react";

export default function AppLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <SessionProvider>
      <div className="flex min-h-screen">
        <SidebarWrapper />
        <div className="flex-1 flex flex-col min-h-screen bg-zinc-950">
          {children}
        </div>
      </div>
    </SessionProvider>
  );
}
