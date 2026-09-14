layout(location = 0) out vec4 fragColor;

void main() {
	vec2 uv = vUV.st * 2.0 - 1.0;
	float d = length(uv);
	// Soft round glow - replaces the point sprite's default hard-edged
	// square with a smooth center-to-edge falloff, so overlapping
	// additive points read as a glowing haze instead of a tiled grid of
	// flat squares (user request 2026-09-03: "qualcosa di piu carino").
	float alpha = smoothstep(1.0, 0.55, d);
	fragColor = TDOutputSwizzle(vec4(vec3(alpha), alpha));
}
