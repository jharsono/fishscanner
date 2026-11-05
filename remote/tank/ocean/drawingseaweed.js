import { Drawing } from "../engine/drawing.js";

export const SEAWEED_TRANSFORM = `
vec4 transform(vec3 p) {
    float pi = 3.14159;
    float A_x = 0.02;
    float A_y = 0.02;
    float w = 10.0 * pi;
    float t = 30.0 * pi / 180.0;
    float wave = sin(w * timer * p.y + t);
    return model * vec4(p.x + wave * A_x, p.y + wave * A_y, p.z, 1.0);
}
`;

/** Sprite for seaweed: a default sprite, all the magic happens in the shader */
export class DrawingSeaweed extends Drawing {}
