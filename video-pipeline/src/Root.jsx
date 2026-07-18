import { Composition } from "remotion";
import { TwoPanelStack } from "./TwoPanelStack.jsx";
import { TOTAL_FRAMES, FPS, WIDTH, HEIGHT } from "./PanelContent.js";

export function Root() {
  return (
    <Composition
      id="TwoPanel"
      component={TwoPanelStack}
      durationInFrames={TOTAL_FRAMES}
      fps={FPS}
      width={WIDTH}
      height={HEIGHT}
    />
  );
}
