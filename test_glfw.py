import glfw
from OpenGL.GL import *
import sys

def main():
    if not glfw.init():
        print("Failed to initialize GLFW")
        return
    
    glfw.window_hint(glfw.CONTEXT_VERSION_MAJOR, 4)
    glfw.window_hint(glfw.CONTEXT_VERSION_MINOR, 1)
    glfw.window_hint(glfw.OPENGL_PROFILE, glfw.OPENGL_CORE_PROFILE)
    glfw.window_hint(glfw.OPENGL_FORWARD_COMPAT, GL_TRUE)
    
    window = glfw.create_window(800, 600, "Black Hole", None, None)
    if not window:
        print("Failed to create window")
        glfw.terminate()
        return
        
    glfw.make_context_current(window)
    print("OpenGL version:", glGetString(GL_VERSION).decode('utf-8'))
    glfw.terminate()

if __name__ == '__main__':
    main()
