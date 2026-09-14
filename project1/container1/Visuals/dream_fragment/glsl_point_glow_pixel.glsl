layout(location = 0) out vec4 fragColor;

void main() {
	vec2 uv = vUV.st * 2.0 - 1.0;
	float d = length(uv);
	// Soft round glow - same technique as soul_geo/glsl_point_glow, kept as
	// its own self-contained copy per this project's per-geo shader
	// convention (no cross-COMP TOP sharing precedent elsewhere).
	float alpha = smoothstep(1.0, 0.55, d);
	fragColor = TDOutputSwizzle(vec4(vec3(alpha), alpha));
}
