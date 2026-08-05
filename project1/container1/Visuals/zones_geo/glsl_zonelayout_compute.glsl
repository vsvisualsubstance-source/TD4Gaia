void main() {
	const uint id = TDIndex();
	if (id >= TDNumElements())
		return;

	const float n = 22.0;
	float angle = 6.28318530718 * (float(id) + 0.5) / n;
	float radius = 2.0;
	P[id] = vec3(radius * cos(angle), radius * sin(angle), 0.0);

	float bright = texelFetch(zoneTex, ivec2(0, int(id)), 0).r / 100.0;
	float motion = texelFetch(zoneTex, ivec2(0, int(id) + 22), 0).r;
	float power  = texelFetch(zoneTex, ivec2(0, int(id) + 44), 0).r;

	vec3 onColor = vec3(1.0, 0.82, 0.45);
	vec3 offColor = vec3(0.10, 0.13, 0.18);
	vec3 col = mix(offColor, onColor, power) * (0.25 + 0.85 * bright);
	col += vec3(1.0, 0.9, 0.6) * motion * 0.6;

	// YOLO presence boost: additive only, existing bright/motion/power untouched
	float presence = 0.0;
	if (id == 5u || id == 6u) presence = uPeopleSalotto;
	else if (id == 3u || id == 4u) presence = uPeopleCorridoio;
	else if (id == 19u || id == 20u || id == 21u) presence = uPeopleIngresso;
	col += vec3(1.0, 0.55, 0.15) * presence * 0.5;

	Color[id] = vec4(col, 1.0);

	PointScale[id] = 0.35 + 1.1 * bright * power + 1.5 * motion + 0.6 * presence;
}
