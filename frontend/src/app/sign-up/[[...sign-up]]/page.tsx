import { SignUp } from "@clerk/nextjs";

export default function SignUpPage() {
  return (
    <div className="relative flex flex-1 items-center justify-center overflow-hidden bg-white py-16">
      <div className="grid-bg pointer-events-none absolute inset-0" />
      <div className="pointer-events-none absolute inset-x-0 top-0 h-[400px] bg-gradient-to-b from-white via-white/70 to-transparent" />
      <div className="relative">
        <SignUp />
      </div>
    </div>
  );
}
