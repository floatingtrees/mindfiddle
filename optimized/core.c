#define PY_SSIZE_T_CLEAN
#include <Python.h>

#include <stdlib.h>
#include <string.h>

#define ERROR_NONE 0
#define ERROR_ALIGNMENT 1
#define ERROR_DATA_RANGE 2

static int
symbol_to_code(Py_UCS4 symbol)
{
    switch (symbol) {
    case '0': return 0;
    case '1': return 1;
    case 's': return 2;
    case 'a': return 3;
    case 'b': return 4;
    case '+': return 5;
    case '<': return 6;
    case '>': return 7;
    case 'X': return 8;
    case '_': return 15;
    default: return -1;
    }
}

static char
code_to_symbol(unsigned int code)
{
    switch (code) {
    case 0: return '0';
    case 1: return '1';
    case 2: return 's';
    case 3: return 'a';
    case 4: return 'b';
    case 5: return '+';
    case 6: return '<';
    case 7: return '>';
    case 8: return 'X';
    default: return '_';
    }
}

static unsigned int
inst_at(const unsigned char *tape, size_t pos)
{
    return (unsigned int)((tape[pos] << 3) | (tape[pos + 1] << 2) |
                          (tape[pos + 2] << 1) | tape[pos + 3]);
}

static size_t
read_literal(const unsigned char *tape, size_t size, size_t start, unsigned int low,
             int *sign)
{
    size_t value = 0;
    size_t pos = start;
    int leading = 1;

    *sign = 1;
    while (pos + 4 <= size) {
        unsigned int code = inst_at(tape, pos);
        if (code != low && code != low + 1) {
            break;
        }
        if (leading) {
            *sign = (code == low) ? -1 : 1;
            leading = 0;
        }
        else {
            value = (value * 2 + (code - low)) % size;
        }
        pos += 4;
    }
    return value;
}

static PyObject *
core_interpret(PyObject *module, PyObject *args, PyObject *kwargs)
{
    static char *keywords[] = {"program", "data_tape", "max_steps", NULL};
    PyObject *program_obj = NULL;
    PyObject *data_tape_obj = NULL;
    Py_ssize_t max_steps = 0;

    if (!PyArg_ParseTupleAndKeywords(args, kwargs, "UOn", keywords,
                                     &program_obj, &data_tape_obj, &max_steps)) {
        return NULL;
    }

    Py_ssize_t symbol_count = PyUnicode_GET_LENGTH(program_obj);
    size_t program_length = (size_t)symbol_count * 4;

    unsigned char *tape =
        (unsigned char *)PyMem_Malloc(program_length > 0 ? program_length : 1);
    if (tape == NULL) {
        return PyErr_NoMemory();
    }

    for (Py_ssize_t index = 0; index < symbol_count; index++) {
        Py_UCS4 symbol = PyUnicode_READ_CHAR(program_obj, index);
        int code = symbol_to_code(symbol);
        if (code < 0) {
            PyObject *key = PyUnicode_FromOrdinal((int)symbol);
            if (key != NULL) {
                PyErr_SetObject(PyExc_KeyError, key);
                Py_DECREF(key);
            }
            PyMem_Free(tape);
            return NULL;
        }
        size_t base = (size_t)index * 4;
        tape[base] = (unsigned char)((code >> 3) & 1);
        tape[base + 1] = (unsigned char)((code >> 2) & 1);
        tape[base + 2] = (unsigned char)((code >> 1) & 1);
        tape[base + 3] = (unsigned char)(code & 1);
    }

    PyObject *data_seq =
        PySequence_Fast(data_tape_obj, "data_tape must be an iterable of bits");
    if (data_seq == NULL) {
        PyMem_Free(tape);
        return NULL;
    }

    Py_ssize_t data_tape_length = PySequence_Fast_GET_SIZE(data_seq);
    size_t size = program_length + (size_t)data_tape_length;

    unsigned char *resized =
        (unsigned char *)PyMem_Realloc(tape, size > 0 ? size : 1);
    if (resized == NULL) {
        Py_DECREF(data_seq);
        PyMem_Free(tape);
        return PyErr_NoMemory();
    }
    tape = resized;

    for (Py_ssize_t index = 0; index < data_tape_length; index++) {
        PyObject *item = PySequence_Fast_GET_ITEM(data_seq, index);
        long bit = PyLong_AsLong(item);
        if (bit == -1 && PyErr_Occurred()) {
            Py_DECREF(data_seq);
            PyMem_Free(tape);
            return NULL;
        }
        if (bit != 0 && bit != 1) {
            Py_DECREF(data_seq);
            PyMem_Free(tape);
            PyErr_SetString(PyExc_ValueError, "data_tape values must be 0 or 1");
            return NULL;
        }
        tape[program_length + (size_t)index] = (unsigned char)bit;
    }
    Py_DECREF(data_seq);

    int error = ERROR_NONE;

    Py_BEGIN_ALLOW_THREADS
    size_t ip = 0;
    size_t ptrs[2];
    int active = 0;

    ptrs[0] = program_length;
    ptrs[1] = program_length;

    for (Py_ssize_t executed = 0; executed < max_steps; executed++) {
        if (ip + 4 > size) {
            error = ERROR_ALIGNMENT;
            break;
        }

        unsigned int code = inst_at(tape, ip);
        int jumped = 0;

        switch (code) {
        case 0:
        case 1: {
            int sign;
            size_t magnitude = read_literal(tape, size, ip, 0, &sign);
            if (ptrs[active] >= size) {
                error = ERROR_DATA_RANGE;
            }
            else if (tape[ptrs[active]] == 0) {
                size_t pos = ptrs[active];
                if (sign > 0) {
                    ptrs[active] = (pos + magnitude) % size;
                }
                else {
                    ptrs[active] = (pos + size - magnitude) % size;
                }
            }
            break;
        }
        case 3:
        case 4: {
            int sign;
            size_t magnitude = read_literal(tape, size, ip, 3, &sign);
            if (ptrs[active] >= size) {
                error = ERROR_DATA_RANGE;
            }
            else if (tape[ptrs[active]] == 0) {
                size_t delta = (magnitude * 4) % size;
                if (sign > 0) {
                    ip = (ip + delta) % size;
                }
                else {
                    ip = (ip + size - delta) % size;
                }
                jumped = 1;
            }
            break;
        }
        case 2:
            active ^= 1;
            break;
        case 5:
            if (ptrs[active] >= size) {
                error = ERROR_DATA_RANGE;
            }
            else {
                tape[ptrs[active]] ^= 1;
            }
            break;
        case 6: {
            size_t pos = ptrs[active];
            if (pos == 0) {
                ptrs[active] = size - 1;
            }
            else if (pos < size) {
                ptrs[active] = pos - 1;
            }
            else {
                ptrs[active] = (pos - 1) % size;
            }
            break;
        }
        case 7: {
            size_t pos = ptrs[active] + 1;
            if (pos < size) {
                ptrs[active] = pos;
            }
            else if (pos == size) {
                ptrs[active] = 0;
            }
            else {
                ptrs[active] = pos % size;
            }
            break;
        }
        case 8:
            goto finished;
        default:
            break;
        }

        if (error != ERROR_NONE) {
            break;
        }
        if (!jumped) {
            ip += 4;
            if (ip >= size) {
                ip -= size;
            }
        }
    }

finished:
    ;
    Py_END_ALLOW_THREADS

    if (error == ERROR_ALIGNMENT) {
        PyMem_Free(tape);
        PyErr_SetString(PyExc_AssertionError, "instructions should be 4 bit");
        return NULL;
    }
    if (error == ERROR_DATA_RANGE) {
        PyMem_Free(tape);
        PyErr_SetString(PyExc_IndexError, "list index out of range");
        return NULL;
    }

    PyObject *inst_tape = PyList_New(symbol_count);
    if (inst_tape == NULL) {
        PyMem_Free(tape);
        return NULL;
    }
    for (Py_ssize_t index = 0; index < symbol_count; index++) {
        char symbol = code_to_symbol(inst_at(tape, (size_t)index * 4));
        PyObject *item = PyUnicode_FromStringAndSize(&symbol, 1);
        if (item == NULL) {
            Py_DECREF(inst_tape);
            PyMem_Free(tape);
            return NULL;
        }
        PyList_SET_ITEM(inst_tape, index, item);
    }

    PyObject *data_tape = PyList_New(data_tape_length);
    if (data_tape == NULL) {
        Py_DECREF(inst_tape);
        PyMem_Free(tape);
        return NULL;
    }
    for (Py_ssize_t index = 0; index < data_tape_length; index++) {
        PyObject *item = PyLong_FromLong((long)tape[program_length + (size_t)index]);
        if (item == NULL) {
            Py_DECREF(data_tape);
            Py_DECREF(inst_tape);
            PyMem_Free(tape);
            return NULL;
        }
        PyList_SET_ITEM(data_tape, index, item);
    }

    PyMem_Free(tape);

    PyObject *result = PyTuple_New(2);
    if (result == NULL) {
        Py_DECREF(data_tape);
        Py_DECREF(inst_tape);
        return NULL;
    }
    PyTuple_SET_ITEM(result, 0, inst_tape);
    PyTuple_SET_ITEM(result, 1, data_tape);
    return result;
}

static PyMethodDef core_methods[] = {
    {"interpret", (PyCFunction)core_interpret, METH_VARARGS | METH_KEYWORDS, NULL},
    {NULL, NULL, 0, NULL},
};

static struct PyModuleDef core_module = {
    PyModuleDef_HEAD_INIT,
    "mindfiddle._core",
    NULL,
    -1,
    core_methods,
    NULL,
    NULL,
    NULL,
    NULL,
};

PyMODINIT_FUNC
PyInit__core(void)
{
    return PyModule_Create(&core_module);
}
