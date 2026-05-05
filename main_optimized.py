import glfw
from OpenGL.GL import *
from OpenGL.GL.shaders import compileProgram, compileShader
import numpy as np
import sys
import time

vertex_shader_source = """
#version 410 core
layout (location = 0) in vec2 aPos;
layout (location = 1) in vec2 aTexCoords;

out vec2 TexCoords;

void main()
{
    gl_Position = vec4(aPos.x, aPos.y, 0.0, 1.0);
    TexCoords = aTexCoords;
}
"""

fragment_shader_source = """
#version 410 core
out vec4 FragColor;
in vec2 TexCoords;

uniform vec2 iResolution;
uniform float iTime;
uniform vec3 iMouse;
uniform float iZoom;

const float M = 1.0;
const float R_s = 2.0 * M;
const float STEP_SIZE = 0.12; 
const int MAX_STEPS = 160;

// High-performance hash and noise
float hash(float n) { return fract(sin(n) * 753.5453123); }

float noise(vec3 x) {
    vec3 p = floor(x);
    vec3 f = fract(x);
    f = f*f*(3.0-2.0*f);
    float n = p.x + p.y*157.0 + 113.0*p.z;
    return mix(mix(mix(hash(n+0.0), hash(n+1.0),f.x),
                   mix(hash(n+157.0), hash(n+158.0),f.x),f.y),
               mix(mix(hash(n+113.0), hash(n+114.0),f.x),
                   mix(hash(n+270.0), hash(n+271.0),f.x),f.y),f.z);
}

float fbm(vec3 p) {
    float f = 0.0;
    f += 0.5000 * noise(p); p = p * 2.02;
    f += 0.2500 * noise(p);
    return f / 0.75;
}

// Cinematic Accretion Disk (The Ring)
vec4 getAccretionDisk(vec3 p) {
    float r = length(p.xz);
    float innerR = 2.6 * M; 
    float outerR = 12.0 * M;
    
    if (r < innerR || r > outerR) return vec4(0.0);
    
    float density = smoothstep(outerR, outerR * 0.4, r) * smoothstep(innerR, innerR * 1.2, r);
    float angle = atan(p.z, p.x);
    float speed = 1.5 / sqrt(r);
    float t = iTime * speed * 1.5;
    
    vec3 uv = vec3(r * 2.5, angle * 4.0 - t, 0.0);
    float n = fbm(uv);
    
    vec3 col = mix(vec3(0.8, 0.2, 0.0), vec3(1.0, 0.8, 0.4), n);
    float alpha = density * (n * 0.8 + 0.2);
    
    return vec4(col * alpha * 4.5, alpha); 
}

vec3 getBackground(vec3 dir) {
    vec3 color = vec3(0.0);
    
    // Giant Blue-White Star (Primary)
    vec3 star1Dir = normalize(vec3(0.4, 0.15, -1.0)); 
    float d1 = dot(dir, star1Dir);
    if (d1 > 0.98) {
        float glow = pow(max(0.0, d1 - 0.98) * 50.0, 4.0);
        float core = smoothstep(0.997, 1.0, d1);
        color += vec3(0.6, 0.7, 1.0) * glow * 1.5;
        color += vec3(1.0, 1.0, 1.0) * core * 5.0;
    }
    
    // Smaller Yellow-White Star (Secondary)
    vec3 star2Dir = normalize(vec3(-0.6, -0.2, -0.8)); 
    float d2 = dot(dir, star2Dir);
    if (d2 > 0.99) {
        float glow = pow(max(0.0, d2 - 0.99) * 100.0, 3.0);
        float core = smoothstep(0.999, 1.0, d2);
        color += vec3(1.0, 0.8, 0.5) * glow * 1.0;
        color += vec3(1.0, 0.9, 0.8) * core * 3.0;
    }
    
    return color;
}

void main() {
    vec2 uv = TexCoords * 2.0 - 1.0;
    uv.x *= iResolution.x / iResolution.y;
    
    // Zoom control
    float camDist = iZoom;
    
    // Camera axis fixed. Only allows horizontal orbit around the black hole's Y-axis.
    float camAngleX = iMouse.x * 0.01 + iTime * 0.02; // Auto-rotate + mouse
    float camAngleY = 0.15; // LOCKED ELEVATION
    
    vec3 ro = vec3(
        camDist * cos(camAngleY) * sin(camAngleX), 
        camDist * sin(camAngleY), 
        camDist * cos(camAngleY) * cos(camAngleX)
    );
    vec3 target = vec3(0.0, 0.0, 0.0);
    
    vec3 cw = normalize(target - ro);
    vec3 cp = vec3(0.0, 1.0, 0.0);
    vec3 cu = normalize(cross(cw, cp));
    vec3 cv = cross(cu, cw);
    
    vec3 rd = normalize(uv.x * cu + uv.y * cv + 1.2 * cw);
    
    vec3 p = ro;
    vec3 v = rd;
    
    float h2 = dot(cross(p, v), cross(p, v));
    
    vec3 color = vec3(0.0);
    float alpha = 1.0;
    
    for (int i = 0; i < MAX_STEPS; i++) {
        float r = length(p);
        
        // Event Horizon 
        if (r < R_s * 1.01) { 
            break;
        }
        
        // Escaped to infinity
        if (r > 35.0) {
            color += alpha * getBackground(normalize(v));
            break; 
        }
        
        float dt = STEP_SIZE * (0.8 + r * 0.2); 
        
        vec3 a = -p * (1.5 * R_s * h2 / (r*r*r*r*r));
        
        v += a * dt;
        vec3 next_p = p + v * dt;
        
        // Accretion Disk Ring
        if ((p.y > 0.0 && next_p.y <= 0.0) || (p.y < 0.0 && next_p.y >= 0.0)) {
            float t_intersect = -p.y / v.y;
            vec3 p_intersect = p + v * t_intersect;
            
            vec4 diskCol = getAccretionDisk(p_intersect);
            
            if (diskCol.a > 0.01) {
                float r_intersect = length(p_intersect.xz);
                vec3 diskVel = normalize(vec3(-p_intersect.z, 0.0, p_intersect.x)) * sqrt(M / r_intersect);
                
                // Relativistic Doppler Beaming
                float doppler = 1.0 / (1.0 - dot(v, diskVel) * 0.85);
                float shift = doppler * doppler;
                
                diskCol.rgb *= vec3(shift * 0.6, shift * 0.9, shift * 1.5);
                diskCol.rgb *= shift;
                
                color += alpha * diskCol.rgb * diskCol.a;
                alpha *= (1.0 - diskCol.a);
                
                if (alpha < 0.05) break;
            }
        }
        
        p = next_p;
    }
    
    // Tonemapping
    color = color / (1.0 + color);
    color = sqrt(color); // Gamma correction
    
    FragColor = vec4(color, 1.0);
}
"""

def main():
    if not glfw.init():
        print("Failed to initialize GLFW")
        return

    glfw.window_hint(glfw.CONTEXT_VERSION_MAJOR, 4)
    glfw.window_hint(glfw.CONTEXT_VERSION_MINOR, 1)
    glfw.window_hint(glfw.OPENGL_PROFILE, glfw.OPENGL_CORE_PROFILE)
    glfw.window_hint(glfw.OPENGL_FORWARD_COMPAT, GL_TRUE)
    glfw.window_hint(glfw.RESIZABLE, GL_TRUE)
    glfw.window_hint(glfw.COCOA_RETINA_FRAMEBUFFER, GL_FALSE)

    window = glfw.create_window(1280, 720, "Fixed Axis Black Hole", None, None)
    if not window:
        print("Failed to create GLFW window")
        glfw.terminate()
        return

    glfw.make_context_current(window)
    glfw.swap_interval(0)

    vertices = np.array([
        -1.0, -1.0,   0.0, 0.0,
         1.0, -1.0,   1.0, 0.0,
        -1.0,  1.0,   0.0, 1.0,
         1.0,  1.0,   1.0, 1.0,
    ], dtype=np.float32)

    VAO = glGenVertexArrays(1)
    VBO = glGenBuffers(1)

    glBindVertexArray(VAO)
    glBindBuffer(GL_ARRAY_BUFFER, VBO)
    glBufferData(GL_ARRAY_BUFFER, vertices.nbytes, vertices, GL_STATIC_DRAW)

    glVertexAttribPointer(0, 2, GL_FLOAT, GL_FALSE, 4 * vertices.itemsize, ctypes.c_void_p(0))
    glEnableVertexAttribArray(0)
    glVertexAttribPointer(1, 2, GL_FLOAT, GL_FALSE, 4 * vertices.itemsize, ctypes.c_void_p(2 * vertices.itemsize))
    glEnableVertexAttribArray(1)

    try:
        shader_program = compileProgram(
            compileShader(vertex_shader_source, GL_VERTEX_SHADER),
            compileShader(fragment_shader_source, GL_FRAGMENT_SHADER)
        )
    except Exception as e:
        print("Shader compilation failed:")
        print(e)
        glfw.terminate()
        return

    glBindBuffer(GL_ARRAY_BUFFER, 0)
    glBindVertexArray(0)

    res_loc = glGetUniformLocation(shader_program, "iResolution")
    time_loc = glGetUniformLocation(shader_program, "iTime")
    mouse_loc = glGetUniformLocation(shader_program, "iMouse")
    zoom_loc = glGetUniformLocation(shader_program, "iZoom")

    cam_angle_x = 0.0
    cam_zoom = 15.0
    
    mouse_pressed = False
    last_mouse_x = 0.0

    def cursor_pos_callback(win, xpos, ypos):
        nonlocal cam_angle_x, last_mouse_x
        if mouse_pressed:
            dx = xpos - last_mouse_x
            # Y-axis movement is completely ignored to lock the rotation axis
            cam_angle_x += dx * 0.5
        last_mouse_x = xpos

    def mouse_button_callback(win, button, action, mods):
        nonlocal mouse_pressed, last_mouse_x
        if button == glfw.MOUSE_BUTTON_LEFT:
            if action == glfw.PRESS:
                mouse_pressed = True
                last_mouse_x, _ = glfw.get_cursor_pos(win)
            elif action == glfw.RELEASE:
                mouse_pressed = False

    def scroll_callback(win, xoffset, yoffset):
        nonlocal cam_zoom
        cam_zoom -= yoffset * 1.5
        cam_zoom = max(4.0, min(50.0, cam_zoom))

    glfw.set_cursor_pos_callback(window, cursor_pos_callback)
    glfw.set_mouse_button_callback(window, mouse_button_callback)
    glfw.set_scroll_callback(window, scroll_callback)

    start_time = time.time()
    last_fps_time = start_time
    frames = 0

    while not glfw.window_should_close(window):
        glfw.poll_events()

        width, height = glfw.get_framebuffer_size(window)
        glViewport(0, 0, width, height)
        glClear(GL_COLOR_BUFFER_BIT)

        glUseProgram(shader_program)

        current_time = time.time() - start_time
        glUniform1f(time_loc, current_time)
        glUniform2f(res_loc, width, height)
        # Passing 0.0 for Y to keep the shader signature consistent, though Y is locked in shader
        glUniform3f(mouse_loc, cam_angle_x, 0.0, 1.0 if mouse_pressed else 0.0)
        glUniform1f(zoom_loc, cam_zoom)

        glBindVertexArray(VAO)
        glDrawArrays(GL_TRIANGLE_STRIP, 0, 4)
        glBindVertexArray(0)

        glfw.swap_buffers(window)
        
        frames += 1
        if time.time() - last_fps_time >= 1.0:
            glfw.set_window_title(window, f"Fixed Axis Black Hole - {frames} FPS")
            frames = 0
            last_fps_time = time.time()

    glfw.terminate()

if __name__ == '__main__':
    main()
