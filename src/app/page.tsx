import ShinyText from "@/components/bits/ShinyText";
import PBNForm from "@/components/PBNForm";
import Image from "next/image";

export default function Home() {
  return (
    <div className="w-full min-w-3xl bg-background">
      <main className="w-full text-foreground p-25">
        <div className="flex-centered flex-col gap-y-4">
          <ShinyText
            text="🎨 Create Your Own Canvas"
            speed={2}
            delay={0}
            color="#973f29"
            shineColor="#f3d1b0"
            spread={120}
            direction="left"
            yoyo={false}
            pauseOnHover={false}
            disabled={false}
            className="text-4xl font-bold"
          />
          <p className="text-xl font-semibold text-muted-foreground">
            Easily generate a paint-by-numbers canvas for free.
          </p>

          <PBNForm />
        </div>
      </main>
    </div>
  );
}
